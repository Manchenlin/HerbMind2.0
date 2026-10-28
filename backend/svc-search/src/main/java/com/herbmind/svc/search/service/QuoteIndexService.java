package com.herbmind.svc.search.service;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import com.herbmind.contract.catalog.LinkVO;
import com.herbmind.contract.search.QuoteIndexItemVO;
import com.herbmind.contract.search.QuoteIndexResultVO;
import com.herbmind.svc.search.util.ChineseText;

/**
 * 条文反向索引：把 classic_quote 的整段原文按「1.xxx(35)」拆成逐条，
 * 再标出引用它的方剂 / 医案（按方名是否出现在条文里匹配）。
 *
 * 说明：真实库的 formula_quote_rel 目前是空表，所以这里用「方名出现在条文文本」
 * 做保守关联；等 ETL 补齐关系表后可换成 relation 精确匹配。
 */
@Service
public class QuoteIndexService {

    private static final int MAX_LINKS = 3;

    /**
     * 真实数据里 568 行条文只有 32 行带「1.xxx(35)」编号，其余是整段无编号原文。
     * 所以这里用 LEFT JOIN LATERAL：有编号的按条拆，无编号的整段作为一条（txt 回退 q.content），
     * 保证 568 条在反向索引里都能被检索到。
     */
    private static final String ARTICLE_SQL = """
            SELECT q.id AS qid, q.page AS page, c.name AS classic_name,
                   b.id AS book_id, b.title AS book_title,
                   m[1] AS seq, COALESCE(m[2], q.content) AS txt, m[3] AS no
            FROM classic_quote q
            JOIN classic c ON c.id = q.classic_id
            JOIN book b ON b.id = c.book_id
            LEFT JOIN LATERAL regexp_matches(q.content,
                '(\\d{1,4})\\s*[.．、]\\s*(.+?)\\s*[(（](\\d{1,4})[)）]', 'gn') AS m ON TRUE
            """;

    private final JdbcTemplate jdbc;

    public QuoteIndexService(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public QuoteIndexResultVO quoteIndex(String q, String bookId, int page, int size) {
        int p = Math.max(1, page);
        int s = Math.min(Math.max(1, size), 100);
        String kw = q == null ? "" : q.trim();
        String book = bookId == null || bookId.isBlank() ? null : bookId.trim();

        StringBuilder where = new StringBuilder(" WHERE 1=1 ");
        List<Object> args = new ArrayList<>();
        if (!kw.isEmpty()) {
            where.append(" AND (COALESCE(m[2], q.content) ILIKE ?");
            args.add("%" + kw + "%");
            for (String t : ChineseText.keywords(kw)) {
                where.append(" OR COALESCE(m[2], q.content) ILIKE ?");
                args.add("%" + t + "%");
            }
            where.append(")");
        }
        if (book != null) {
            where.append(" AND b.id = ?");
            args.add(book);
        }

        long total = 0;
        try {
            Long c = jdbc.queryForObject("SELECT count(*) FROM (" + ARTICLE_SQL + where + ") t",
                    Long.class, args.toArray());
            total = c == null ? 0 : c;
        } catch (Exception e) {
            return new QuoteIndexResultVO(List.of(), 0, p, s);
        }

        List<Object> pageArgs = new ArrayList<>(args);
        pageArgs.add(s);
        pageArgs.add((p - 1) * s);

        List<Map<String, Object>> rows;
        try {
            rows = jdbc.queryForList(ARTICLE_SQL + where
                    + " ORDER BY NULLIF(m[3], '')::int NULLS LAST,"
                    + " NULLIF(m[1], '')::int NULLS LAST, q.id LIMIT ? OFFSET ?", pageArgs.toArray());
        } catch (Exception e) {
            return new QuoteIndexResultVO(List.of(), total, p, s);
        }

        List<FormulaRef> formulas = loadFormulas();
        List<CaseRef> cases = loadCases();
        List<QuoteIndexItemVO> list = new ArrayList<>();
        Set<String> seen = new LinkedHashSet<>();
        for (Map<String, Object> row : rows) {
            String qid = str(row.get("qid"));
            String no = str(row.get("no"));
            String key = qid + "#" + no;
            if (!seen.add(key)) {
                continue;
            }
            String text = ChineseText.clean(str(row.get("txt")));
            List<LinkVO> fl = matchFormulas(text, formulas);
            List<LinkVO> cl = matchCases(text, fl, cases);
            list.add(new QuoteIndexItemVO(qid, str(row.get("classic_name")), no, text,
                    str(row.get("page")), fl, cl));
        }
        return new QuoteIndexResultVO(list, total, p, s);
    }

    private List<LinkVO> matchFormulas(String text, List<FormulaRef> formulas) {
        List<LinkVO> out = new ArrayList<>();
        Set<String> ids = new LinkedHashSet<>();
        for (FormulaRef f : formulas) {
            for (String name : f.names) {
                if (text.contains(name)) {
                    if (ids.add(f.id)) {
                        out.add(new LinkVO(f.id, f.name));
                    }
                    break;
                }
            }
            if (out.size() >= MAX_LINKS) {
                break;
            }
        }
        return out;
    }

    private List<LinkVO> matchCases(String text, List<LinkVO> formulas, List<CaseRef> cases) {
        Set<String> formulaIds = new LinkedHashSet<>();
        for (LinkVO l : formulas) {
            formulaIds.add(l.id());
        }
        List<LinkVO> out = new ArrayList<>();
        for (CaseRef c : cases) {
            if (out.size() >= MAX_LINKS) {
                break;
            }
            boolean byFormula = c.mainFormulaId != null && formulaIds.contains(c.mainFormulaId);
            boolean byTitle = c.shortTitle != null && c.shortTitle.length() >= 2
                    && text.contains(c.shortTitle);
            if (byFormula || byTitle) {
                out.add(new LinkVO(c.id, c.title));
            }
        }
        return out;
    }

    private List<FormulaRef> loadFormulas() {
        List<FormulaRef> out = new ArrayList<>();
        try {
            for (Map<String, Object> row : jdbc.queryForList("SELECT id, name, alias FROM formula")) {
                String name = str(row.get("name"));
                String alias = str(row.get("alias"));
                List<String> names = new ArrayList<>();
                addNames(names, name);
                addNames(names, alias);
                out.add(new FormulaRef(str(row.get("id")), name, names));
            }
        } catch (Exception e) {
            // 检索降级：没有方剂表也能列出条文
        }
        return out;
    }

    private List<CaseRef> loadCases() {
        List<CaseRef> out = new ArrayList<>();
        try {
            for (Map<String, Object> row : jdbc.queryForList(
                    "SELECT id, title, main_formula_id FROM case_record")) {
                String title = str(row.get("title"));
                String shortTitle = title;
                if (title != null) {
                    int cut = title.indexOf('·');
                    if (cut > 0) {
                        shortTitle = title.substring(0, cut).trim();
                    }
                }
                out.add(new CaseRef(str(row.get("id")), title, shortTitle,
                        str(row.get("main_formula_id"))));
            }
        } catch (Exception e) {
            // 同上
        }
        return out;
    }

    private void addNames(List<String> names, String raw) {
        if (raw == null || raw.isBlank()) {
            return;
        }
        for (String part : raw.split("[、,，/；;]")) {
            String p = part.trim();
            if (p.length() >= 2 && !names.contains(p)) {
                names.add(p);
            }
        }
    }

    private static String str(Object o) {
        return o == null ? null : String.valueOf(o);
    }

    private record FormulaRef(String id, String name, List<String> names) {
    }

    private record CaseRef(String id, String title, String shortTitle, String mainFormulaId) {
    }
}
