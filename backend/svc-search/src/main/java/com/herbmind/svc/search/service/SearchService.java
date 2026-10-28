package com.herbmind.svc.search.service;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.herbmind.contract.search.FacetsVO;
import com.herbmind.contract.search.SearchHitVO;
import com.herbmind.contract.search.SearchRequest;
import com.herbmind.contract.search.SearchResultVO;
import com.herbmind.svc.search.util.ChineseText;

/**
 * 混合召回（本域核心件）。
 *
 * 四条召回腿，按 RRF（Reciprocal Rank Fusion）融合：
 *   ① 向量：pgvector 余弦（查询向量由 EmbeddingClient 生成，未配置则跳过）
 *   ② 全文：pg_jieba + ts_rank_cd（未装分词器时该腿为 0 行，不影响其它腿）
 *   ③ 词项：中文 2-gram / 短查询整词 ILIKE（pg_jieba 缺失时的主力，保证「麻黄汤」能命中）
 *   ④ 条文：classic_quote 里的编号原文按正则拆条后匹配（条文不在 content_unit 中）
 *
 * 每条腿独立 try/catch：任何一条腿失败（扩展没装 / SQL 报错）都只降级，不让接口 5xx。
 * score 为 0–1 的相关度（单腿最佳 + 多腿加成），用于展示；排序用 RRF。
 */
@Service
public class SearchService {

    private static final Logger log = LoggerFactory.getLogger(SearchService.class);

    private static final int LEG_LIMIT = 200;
    private static final int MAX_SIZE = 50;
    private static final int RRF_K = 60;

    private static final String UNIT_COLS =
            "id, book_id, ref_type, ref_id, title, content, meta_jsonb";

    private static final RowMapper<UnitRow> UNIT_MAPPER = (rs, i) -> new UnitRow(
            rs.getString("id"),
            rs.getString("book_id"),
            rs.getString("ref_type"),
            rs.getString("ref_id"),
            rs.getString("title"),
            rs.getString("content"),
            rs.getString("meta_jsonb"));

    private final JdbcTemplate jdbc;
    private final EmbeddingClient embedding;
    private final ObjectMapper json = new ObjectMapper();
    private volatile Map<String, String> bookCache = Map.of();
    private volatile long bookCacheAt = 0L;

    public SearchService(JdbcTemplate jdbc, EmbeddingClient embedding) {
        this.jdbc = jdbc;
        this.embedding = embedding;
    }

    public SearchResultVO search(SearchRequest req) {
        long t0 = System.currentTimeMillis();
        String q = req.q() == null ? "" : req.q().trim();
        int page = req.page() == null || req.page() < 1 ? 1 : req.page();
        int size = req.size() == null || req.size() < 1 ? 10 : Math.min(req.size(), MAX_SIZE);
        String type = normalizeType(req.type());
        String bookId = blankToNull(req.bookId());
        String nodeId = blankToNull(req.nodeId());
        String herb = blankToNull(req.herb());

        Map<String, Candidate> cands = new LinkedHashMap<>();
        boolean vectorUsed = false;
        boolean fulltextHit = false;
        List<String> tokens = ChineseText.keywords(q);

        if (!q.isEmpty()) {
            float[] qv = embedding.embed(q);
            if (qv != null) {
                vectorUsed = runVector(qv, bookId, nodeId, herb, cands);
            }
            fulltextHit = runFulltext(q, bookId, nodeId, herb, cands);
            runFuzzy(tokens, q, bookId, nodeId, herb, cands);
            // 条文没有目录归属，按节点筛选时不参与
            if (herb == null && nodeId == null) {
                runQuotes(q, tokens, bookId, cands);
            }
        }

        // 排序：RRF 融合分（多腿命中优先），再按最佳单腿分，最后按类型（方剂 > 医案 > 条文）
        List<Candidate> sorted = new ArrayList<>(cands.values());
        sorted.sort(Comparator.comparingDouble((Candidate c) -> c.rrf).reversed()
                .thenComparing(Comparator.comparingDouble((Candidate c) -> c.best).reversed())
                .thenComparingInt(c -> typeOrder(c.refType))
                .thenComparing(c -> c.title == null ? "" : c.title));

        FacetsVO facets = q.isEmpty() ? facetCountsFromDb() : buildFacets(sorted);

        List<Candidate> filtered = new ArrayList<>();
        for (Candidate c : sorted) {
            if (type == null || "all".equals(type) || type.equals(c.refType)) {
                filtered.add(c);
            }
        }

        int from = Math.min((page - 1) * size, filtered.size());
        int to = Math.min(from + size, filtered.size());
        List<Candidate> slice = filtered.subList(from, to);
        enrichTitles(slice);
        Map<String, List<String>> herbMap = loadHerbs(slice);

        List<SearchHitVO> hits = new ArrayList<>();
        for (Candidate c : slice) {
            double score = Math.min(0.99, c.best + 0.03 * Math.max(0, c.legs.size() - 1));
            score = Math.round(score * 100) / 100.0;
            String snippet = ChineseText.snippet(c.content, q);
            hits.add(new SearchHitVO(
                    c.id, c.refType, c.refId, c.title, snippet, score,
                    c.bookId, c.bookTitle, c.classic, c.chapter, c.section, c.page,
                    "formula".equals(c.refType) ? herbMap.getOrDefault(c.refId, List.of()) : List.of(),
                    new ArrayList<>(c.legs),
                    c.meta));
        }

        String mode;
        if (q.isEmpty()) {
            mode = "browse";
        } else if (vectorUsed) {
            mode = "hybrid";
        } else if (fulltextHit) {
            mode = "fulltext";
        } else {
            mode = "fuzzy";
        }

        return new SearchResultVO(hits, filtered.size(), page, size, mode,
                System.currentTimeMillis() - t0, facets);
    }

    public FacetsVO facets(String q, String bookId) {
        SearchResultVO r = search(new SearchRequest(q, null, bookId, null, null, 1, 1));
        return r.facets();
    }

    // ==================== 四条召回腿 ====================

    private boolean runVector(float[] qv, String bookId, String nodeId, String herb,
                              Map<String, Candidate> out) {
        String lit = EmbeddingClient.toLiteral(qv);
        if (lit == null) {
            return false;
        }
        try {
            StringBuilder sql = new StringBuilder("SELECT ").append(UNIT_COLS)
                    .append(", 1 - (embedding <=> '").append(lit).append("'::vector) AS s")
                    .append(" FROM content_unit WHERE embedding IS NOT NULL");
            List<Object> args = new ArrayList<>();
            appendUnitFilters(sql, args, bookId, nodeId, herb);
            sql.append(" ORDER BY embedding <=> '").append(lit).append("'::vector LIMIT ").append(LEG_LIMIT);

            List<Map<String, Object>> rows = jdbc.queryForList(sql.toString(), args.toArray());
            int rank = 1;
            for (Map<String, Object> row : rows) {
                Candidate c = unitCandidate(row);
                c.rrf = 1.0 / (RRF_K + rank++);
                c.best = Math.max(c.best, toDouble(row.get("s")));
                c.legs.add("vector");
                merge(out, c);
            }
            return !rows.isEmpty();
        } catch (Exception e) {
            log.warn("向量召回腿失败（已跳过）：{}", e.getMessage());
            return false;
        }
    }

    private boolean runFulltext(String q, String bookId, String nodeId, String herb,
                                Map<String, Candidate> out) {
        try {
            StringBuilder sql = new StringBuilder("SELECT ").append(UNIT_COLS)
                    .append(", ts_rank_cd(search_tsv, plainto_tsquery('jiebacfg', ?)) AS s")
                    .append(" FROM content_unit WHERE search_tsv @@ plainto_tsquery('jiebacfg', ?)");
            List<Object> args = new ArrayList<>();
            args.add(q);
            args.add(q);
            appendUnitFilters(sql, args, bookId, nodeId, herb);
            sql.append(" ORDER BY s DESC LIMIT ").append(LEG_LIMIT);

            List<Map<String, Object>> rows = jdbc.queryForList(sql.toString(), args.toArray());
            int rank = 1;
            for (Map<String, Object> row : rows) {
                Candidate c = unitCandidate(row);
                c.rrf = 1.0 / (RRF_K + rank++);
                double s = toDouble(row.get("s"));
                c.best = Math.max(c.best, Math.min(0.95, 0.5 + s));
                c.legs.add("fulltext");
                merge(out, c);
            }
            return !rows.isEmpty();
        } catch (Exception e) {
            // 常见：pg_jieba 未安装（没有 jiebacfg 配置）→ 走词项腿兜底
            log.debug("全文召回腿不可用（已跳过）：{}", e.getMessage());
            return false;
        }
    }

    private void runFuzzy(List<String> tokens, String q, String bookId, String nodeId,
                          String herb, Map<String, Candidate> out) {
        if (tokens.isEmpty()) {
            return;
        }
        try {
            StringBuilder sql = new StringBuilder("SELECT ").append(UNIT_COLS)
                    .append(" FROM content_unit WHERE (");
            List<Object> args = new ArrayList<>();
            for (int i = 0; i < tokens.size(); i++) {
                if (i > 0) {
                    sql.append(" OR ");
                }
                sql.append("content ILIKE ? OR title ILIKE ?");
                args.add("%" + tokens.get(i) + "%");
                args.add("%" + tokens.get(i) + "%");
            }
            sql.append(")");
            appendUnitFilters(sql, args, bookId, nodeId, herb);
            sql.append(" LIMIT 400");

            List<UnitRow> rows = jdbc.query(sql.toString(), UNIT_MAPPER, args.toArray());
            List<Scored> scored = new ArrayList<>();
            for (UnitRow u : rows) {
                String hay = (u.content == null ? "" : u.content) + " " + (u.title == null ? "" : u.title);
                int matched = 0;
                for (String t : tokens) {
                    if (hay.contains(t)) {
                        matched++;
                    }
                }
                if (matched == 0) {
                    continue;
                }
                double sim = (double) matched / tokens.size();
                if (q.length() >= 2 && hay.contains(q)) {
                    sim = Math.max(sim, 0.98);
                }
                scored.add(new Scored(u, sim));
            }
            scored.sort(Comparator.comparingDouble((Scored s) -> s.sim).reversed());
            int rank = 1;
            for (Scored s : scored) {
                Candidate c = unitCandidate(s.unit);
                c.rrf = 1.0 / (RRF_K + rank++);
                c.best = Math.max(c.best, s.sim);
                c.legs.add("fuzzy");
                merge(out, c);
            }
        } catch (Exception e) {
            log.warn("词项召回腿失败（已跳过）：{}", e.getMessage());
        }
    }

    private void runQuotes(String q, List<String> tokens, String bookId, Map<String, Candidate> out) {
        if (tokens.isEmpty()) {
            return;
        }
        try {
            StringBuilder sql = new StringBuilder("""
                    SELECT q.id AS qid, q.page AS page, c.name AS classic_name,
                           b.id AS book_id, b.title AS book_title,
                           m[1] AS seq, m[2] AS txt, m[3] AS no,
                           word_similarity(?, m[2]) AS s
                    FROM classic_quote q
                    JOIN classic c ON c.id = q.classic_id
                    JOIN book b ON b.id = c.book_id
                    CROSS JOIN LATERAL regexp_matches(q.content,
                        '(\\d{1,4})\\s*[.．、]\\s*(.+?)\\s*[(（](\\d{1,4})[)）]', 'gn') AS m
                    WHERE (""");
            List<Object> args = new ArrayList<>();
            args.add(q);
            for (int i = 0; i < tokens.size(); i++) {
                if (i > 0) {
                    sql.append(" OR ");
                }
                sql.append("m[2] ILIKE ?");
                args.add("%" + tokens.get(i) + "%");
            }
            sql.append(")");
            if (bookId != null) {
                sql.append(" AND b.id = ?");
                args.add(bookId);
            }
            sql.append(" ORDER BY s DESC LIMIT 120");

            List<Map<String, Object>> rows = jdbc.queryForList(sql.toString(), args.toArray());
            int rank = 1;
            for (Map<String, Object> row : rows) {
                String qid = str(row.get("qid"));
                String no = str(row.get("no"));
                String txt = str(row.get("txt"));
                String classicName = str(row.get("classic_name"));
                Candidate c = new Candidate();
                c.id = "q:" + qid + "#" + no;
                c.refType = "quote";
                c.refId = qid;
                c.title = (classicName == null ? "条文" : "《" + classicName + "》")
                        + (no == null ? "" : "第 " + no + " 条");
                c.content = txt;
                c.bookId = str(row.get("book_id"));
                c.bookTitle = str(row.get("book_title"));
                c.classic = classicName;
                c.page = str(row.get("page"));
                c.meta = Map.of("page", c.page == null ? "" : c.page);
                c.rrf = 1.0 / (RRF_K + rank++);
                c.best = Math.max(c.best, Math.min(0.97, toDouble(row.get("s"))));
                c.legs.add("quote");
                merge(out, c);
            }
        } catch (Exception e) {
            log.warn("条文召回腿失败（已跳过）：{}", e.getMessage());
        }
    }

    // ==================== 辅助 ====================

    /** 同一条内容被多条腿召回时合并：RRF 累加、取最佳单腿分、合并命中腿集合。 */
    private void merge(Map<String, Candidate> out, Candidate fresh) {
        Candidate exist = out.get(fresh.id);
        if (exist == null) {
            out.put(fresh.id, fresh);
            return;
        }
        exist.rrf += fresh.rrf;
        exist.best = Math.max(exist.best, fresh.best);
        exist.legs.addAll(fresh.legs);
    }

    /** 空查询时的分面：直接数全库，让检索页打开就有数。 */
    private FacetsVO facetCountsFromDb() {
        Map<String, Long> types = new LinkedHashMap<>();
        types.put("formula", scalar("SELECT count(*) FROM formula"));
        types.put("case", scalar("SELECT count(*) FROM case_record"));
        types.put("quote", scalar("SELECT count(*) FROM classic_quote"));

        Map<String, Long> books = new LinkedHashMap<>();
        Map<String, Long> classics = new LinkedHashMap<>();
        try {
            for (Map<String, Object> row : jdbc.queryForList(
                    "SELECT b.title AS k, count(cu.id) AS c FROM book b"
                            + " LEFT JOIN content_unit cu ON cu.book_id = b.id"
                            + " GROUP BY b.title ORDER BY c DESC")) {
                books.put(str(row.get("k")), ((Number) row.get("c")).longValue());
            }
            for (Map<String, Object> row : jdbc.queryForList(
                    "SELECT c.name AS k, count(q.id) AS c FROM classic c"
                            + " LEFT JOIN classic_quote q ON q.classic_id = c.id"
                            + " GROUP BY c.name ORDER BY c DESC")) {
                classics.put(str(row.get("k")), ((Number) row.get("c")).longValue());
            }
        } catch (Exception e) {
            log.debug("分面统计失败：{}", e.getMessage());
        }
        return new FacetsVO(types, classics, books);
    }

    private long scalar(String sql) {
        try {
            Long v = jdbc.queryForObject(sql, Long.class);
            return v == null ? 0 : v;
        } catch (Exception e) {
            return 0;
        }
    }

    private void appendUnitFilters(StringBuilder sql, List<Object> args, String bookId,
                                   String nodeId, String herb) {
        if (bookId != null) {
            sql.append(" AND book_id = ?");
            args.add(bookId);
        }
        if (nodeId != null) {
            // 递归取该节点及其所有后代，再映射到方剂 / 医案（条文与目录无关）
            sql.append(" AND ref_id IN (")
                    .append("WITH RECURSIVE t AS (")
                    .append(" SELECT id FROM book_node WHERE id = ?")
                    .append(" UNION ALL")
                    .append(" SELECT n.id FROM book_node n JOIN t ON n.parent_id = t.id)")
                    .append(" SELECT f.id FROM formula f JOIN t ON f.node_id = t.id")
                    .append(" UNION")
                    .append(" SELECT c.id FROM case_record c JOIN formula f2 ON c.main_formula_id = f2.id")
                    .append(" JOIN t ON f2.node_id = t.id)")
                    .append("");
            args.add(nodeId);
        }
        if (herb != null) {
            sql.append(" AND ref_id IN (SELECT formula_id FROM formula_herb WHERE herb_name ILIKE ?)");
            args.add("%" + herb + "%");
        }
    }

    private Candidate unitCandidate(Map<String, Object> row) {
        UnitRow u = new UnitRow(str(row.get("id")), str(row.get("book_id")),
                str(row.get("ref_type")), str(row.get("ref_id")), str(row.get("title")),
                str(row.get("content")), str(row.get("meta_jsonb")));
        return unitCandidate(u);
    }

    private Candidate unitCandidate(UnitRow u) {
        Candidate c = new Candidate();
        c.id = u.id;
        c.refType = u.refType;
        c.refId = u.refId;
        c.title = u.title;
        c.content = u.content;
        c.bookId = u.bookId;
        c.meta = parseMeta(u.metaJson);
        c.page = c.meta.get("page") == null ? null : String.valueOf(c.meta.get("page"));
        c.chapter = c.meta.get("chapter") == null ? null : String.valueOf(c.meta.get("chapter"));
        c.section = c.meta.get("section") == null ? null : String.valueOf(c.meta.get("section"));
        c.classic = c.meta.get("classic") == null ? null : String.valueOf(c.meta.get("classic"));
        Map<String, String> books = bookTitles();
        c.bookTitle = books.get(c.bookId);
        return c;
    }

    /**
     * content_unit.title 对医案来说是书名（如「伤寒论」），直接展示没有意义。
     * 这里按 ref_id 回查真实标题：医案取 case_record.title，方剂取 formula.name。
     */
    private void enrichTitles(List<Candidate> slice) {
        List<String> caseIds = slice.stream()
                .filter(c -> "case".equals(c.refType) && c.refId != null)
                .map(c -> c.refId).distinct().toList();
        List<String> formulaIds = slice.stream()
                .filter(c -> "formula".equals(c.refType) && c.refId != null)
                .map(c -> c.refId).distinct().toList();

        Map<String, String> caseTitles = lookup("SELECT id, title FROM case_record WHERE id IN (", caseIds);
        Map<String, String> formulaNames = lookup("SELECT id, name FROM formula WHERE id IN (", formulaIds);

        for (Candidate c : slice) {
            if ("case".equals(c.refType)) {
                String t = caseTitles.get(c.refId);
                if (t != null && !t.isBlank()) {
                    c.title = t;
                }
            } else if ("formula".equals(c.refType)) {
                String t = formulaNames.get(c.refId);
                if (t != null && !t.isBlank()) {
                    c.title = t;
                }
            }
        }
    }

    private Map<String, String> lookup(String sqlPrefix, List<String> ids) {
        Map<String, String> out = new HashMap<>();
        if (ids.isEmpty()) {
            return out;
        }
        try {
            String sql = sqlPrefix + String.join(",", ids.stream().map(x -> "?").toList()) + ")";
            for (Map<String, Object> row : jdbc.queryForList(sql, ids.toArray())) {
                String id = str(row.get("id"));
                Object v = row.get("title") != null ? row.get("title") : row.get("name");
                if (id != null && v != null) {
                    out.put(id, String.valueOf(v));
                }
            }
        } catch (Exception e) {
            log.debug("回查标题失败：{}", e.getMessage());
        }
        return out;
    }

    private Map<String, String> bookTitles() {        long now = System.currentTimeMillis();
        if (!bookCache.isEmpty() && now - bookCacheAt < 60_000) {
            return bookCache;
        }
        Map<String, String> out = new HashMap<>();
        try {
            for (Map<String, Object> row : jdbc.queryForList("SELECT id, title FROM book")) {
                out.put(str(row.get("id")), str(row.get("title")));
            }
            bookCache = out;
            bookCacheAt = now;
        } catch (Exception e) {
            log.debug("读取 book 表失败：{}", e.getMessage());
        }
        return out;
    }

    private Map<String, List<String>> loadHerbs(List<Candidate> slice) {
        List<String> ids = slice.stream()
                .filter(c -> "formula".equals(c.refType) && c.refId != null)
                .map(c -> c.refId)
                .distinct()
                .toList();
        Map<String, List<String>> out = new HashMap<>();
        if (ids.isEmpty()) {
            return out;
        }
        try {
            StringBuilder sql = new StringBuilder(
                    "SELECT formula_id, herb_name FROM formula_herb WHERE formula_id IN (");
            sql.append(String.join(",", ids.stream().map(x -> "?").toList())).append(") ORDER BY seq");
            for (Map<String, Object> row : jdbc.queryForList(sql.toString(), ids.toArray())) {
                out.computeIfAbsent(str(row.get("formula_id")), k -> new ArrayList<>())
                        .add(str(row.get("herb_name")));
            }
        } catch (Exception e) {
            log.debug("读取药味失败：{}", e.getMessage());
        }
        return out;
    }

    private FacetsVO buildFacets(List<Candidate> all) {
        Map<String, Long> types = new LinkedHashMap<>();
        Map<String, Long> classics = new LinkedHashMap<>();
        Map<String, Long> books = new LinkedHashMap<>();
        for (Candidate c : all) {
            types.merge(c.refType == null ? "unknown" : c.refType, 1L, Long::sum);
            if (c.classic != null) {
                classics.merge(c.classic, 1L, Long::sum);
            }
            if (c.bookTitle != null) {
                books.merge(c.bookTitle, 1L, Long::sum);
            }
        }
        return new FacetsVO(sortByCount(types), sortByCount(classics), sortByCount(books));
    }

    private Map<String, Long> sortByCount(Map<String, Long> in) {
        List<Map.Entry<String, Long>> list = new ArrayList<>(in.entrySet());
        list.sort(Map.Entry.<String, Long>comparingByValue().reversed());
        Map<String, Long> out = new LinkedHashMap<>();
        for (Map.Entry<String, Long> e : list) {
            out.put(e.getKey(), e.getValue());
        }
        return out;
    }

    private Map<String, Object> parseMeta(String s) {
        if (s == null || s.isBlank()) {
            return Map.of();
        }
        try {
            return json.readValue(s, new com.fasterxml.jackson.core.type.TypeReference<Map<String, Object>>() {
            });
        } catch (Exception e) {
            return Map.of();
        }
    }

    private static String normalizeType(String type) {
        if (type == null || type.isBlank() || "all".equalsIgnoreCase(type)) {
            return null;
        }
        String t = type.trim().toLowerCase(Locale.ROOT);
        return List.of("formula", "case", "quote").contains(t) ? t : null;
    }

    private static String blankToNull(String s) {
        return s == null || s.isBlank() ? null : s.trim();
    }

    /** 09 §2「按类型排序」：同分时 方剂 > 医案 > 条文。 */
    private static int typeOrder(String refType) {
        if (refType == null) {
            return 9;
        }
        return switch (refType) {
            case "formula" -> 0;
            case "case" -> 1;
            case "quote" -> 2;
            default -> 9;
        };
    }

    private static String str(Object o) {
        return o == null ? null : String.valueOf(o);
    }

    private static double toDouble(Object o) {
        if (o instanceof Number n) {
            return n.doubleValue();
        }
        try {
            return o == null ? 0 : Double.parseDouble(String.valueOf(o));
        } catch (NumberFormatException e) {
            return 0;
        }
    }

    private record UnitRow(String id, String bookId, String refType, String refId,
                           String title, String content, String metaJson) {
    }

    private record Scored(UnitRow unit, double sim) {
    }

    /** 检索中间态：RRF 融合分 + 单腿最佳分 + 命中腿集合。 */
    private static final class Candidate {
        String id;
        String refType;
        String refId;
        String title;
        String content;
        String bookId;
        String bookTitle;
        String classic;
        String chapter;
        String section;
        String page;
        Map<String, Object> meta = Map.of();
        double rrf;
        double best;
        Set<String> legs = new LinkedHashSet<>();
    }
}
