package com.herbmind.svc.insight.service;

import java.nio.charset.StandardCharsets;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import com.herbmind.contract.insight.CountItemVO;
import com.herbmind.contract.insight.HerbStatVO;
import com.herbmind.contract.insight.ResearchPackVO;
import com.herbmind.contract.insight.TrendVO;

/**
 * 科研统计（域1 · 只读）。
 *
 * 数据全部来自内容域自己的表（formula / formula_herb / book_node / classic_quote /
 * content_unit），不跨域直读域2 的练习表——练习相关的统计等域2 接口就绪后由 BFF 组合。
 */
@Service
public class InsightService {

    private static final DateTimeFormatter ISO = DateTimeFormatter.ISO_OFFSET_DATE_TIME;

    private final JdbcTemplate jdbc;

    public InsightService(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public List<HerbStatVO> herbs(int limit, String bookId) {
        int n = Math.min(Math.max(1, limit), 100);
        String book = bookId == null || bookId.isBlank() ? null : bookId;

        String base = """
                FROM formula_herb fh
                JOIN formula f ON f.id = fh.formula_id
                """;
        String where = "";
        List<Object> args = new ArrayList<>();
        if (book != null) {
            base += " JOIN book_node nd ON nd.id = f.node_id ";
            where = " WHERE nd.book_id = ? ";
            args.add(book);
        }

        long totalFormulas = count("SELECT count(DISTINCT fh.formula_id) " + base + where, args);

        String sql = "SELECT fh.herb_name AS herb, count(*) AS cnt,"
                + " count(DISTINCT fh.formula_id) AS fcnt " + base + where
                + " GROUP BY fh.herb_name ORDER BY cnt DESC, fh.herb_name LIMIT ?";
        List<Object> qargs = new ArrayList<>(args);
        qargs.add(n);

        List<HerbStatVO> out = new ArrayList<>();
        for (Map<String, Object> row : jdbc.queryForList(sql, qargs.toArray())) {
            long fcnt = num(row.get("fcnt"));
            double ratio = totalFormulas == 0 ? 0 : round((double) fcnt / totalFormulas);
            out.add(new HerbStatVO(str(row.get("herb")), num(row.get("cnt")), fcnt, ratio));
        }
        return out;
    }

    /**
     * 证候分布：按目录里的「类方证」节点统计方剂数（真实数据的证候层级就是 n_g* 分类节点）。
     */
    public List<CountItemVO> syndrome(int limit) {
        int n = Math.min(Math.max(1, limit), 50);
        String sql = """
                SELECT nd.id AS id, nd.title AS title, count(f.id) AS cnt
                FROM book_node nd
                LEFT JOIN formula f ON f.node_id = nd.id
                WHERE nd.node_type IN ('category', 'section')
                GROUP BY nd.id, nd.title
                HAVING count(f.id) > 0
                ORDER BY cnt DESC, nd.title
                LIMIT ?
                """;
        long total = count("SELECT count(*) FROM formula WHERE node_id IS NOT NULL", List.of());
        List<CountItemVO> out = new ArrayList<>();
        for (Map<String, Object> row : jdbc.queryForList(sql, n)) {
            long cnt = num(row.get("cnt"));
            out.add(new CountItemVO(str(row.get("id")), str(row.get("title")), cnt,
                    total == 0 ? 0 : round((double) cnt / total)));
        }
        return out;
    }

    public TrendVO trend() {
        Map<String, Long> books = group(
                "SELECT b.title AS k, count(cu.id) AS c FROM book b"
                        + " LEFT JOIN content_unit cu ON cu.book_id = b.id"
                        + " GROUP BY b.title ORDER BY c DESC");
        Map<String, Long> chapters = group("""
                SELECT COALESCE(meta_jsonb->>'section', meta_jsonb->>'chapter') AS k, count(*) AS c
                FROM content_unit
                WHERE COALESCE(meta_jsonb->>'section', meta_jsonb->>'chapter') IS NOT NULL
                GROUP BY 1 ORDER BY c DESC LIMIT 20
                """);

        long totalUnits = count("SELECT count(*) FROM content_unit", List.of());
        long totalFormulas = count("SELECT count(*) FROM formula", List.of());
        long totalCases = count("SELECT count(*) FROM case_record", List.of());
        long totalQuotes = count("SELECT count(*) FROM classic_quote", List.of());

        return new TrendVO(toItems(books, totalUnits), toItems(chapters, totalUnits),
                totalUnits, totalFormulas, totalCases, totalQuotes);
    }

    /** 导出：csv（默认）或 json 文本，UTF-8 BOM 方便 Excel 直接打开。 */
    public byte[] export(String format, String kind) {
        String k = kind == null || kind.isBlank() ? "herbs" : kind.trim();
        String f = format == null || format.isBlank() ? "csv" : format.trim().toLowerCase();

        List<String> header = new ArrayList<>();
        List<List<String>> rows = new ArrayList<>();

        switch (k) {
            case "formulas" -> {
                header.addAll(List.of("id", "name", "efficacy", "syndrome", "page", "herbs"));
                for (Map<String, Object> r : jdbc.queryForList("""
                        SELECT f.id, f.name, f.efficacy, f.syndrome_text, f.page,
                               string_agg(fh.herb_name || coalesce(fh.dose::text, '') || coalesce(fh.unit, ''),
                                          '、' ORDER BY fh.seq) AS herbs
                        FROM formula f
                        LEFT JOIN formula_herb fh ON fh.formula_id = f.id
                        GROUP BY f.id, f.name, f.efficacy, f.syndrome_text, f.page
                        ORDER BY f.id
                        """)) {
                    rows.add(java.util.Arrays.asList(nz(r.get("id")), nz(r.get("name")), nz(r.get("efficacy")),
                            nz(r.get("syndrome_text")), nz(r.get("page")), nz(r.get("herbs"))));
                }
            }
            case "quotes" -> {
                header.addAll(List.of("id", "classic", "articleNo", "page", "content"));
                for (Map<String, Object> r : jdbc.queryForList("""
                        SELECT q.id, c.name AS classic, q.article_no, q.page, q.content
                        FROM classic_quote q LEFT JOIN classic c ON c.id = q.classic_id
                        ORDER BY q.id
                        """)) {
                    rows.add(java.util.Arrays.asList(nz(r.get("id")), nz(r.get("classic")), nz(r.get("article_no")),
                            nz(r.get("page")), nz(r.get("content"))));
                }
            }
            case "units" -> {
                header.addAll(List.of("id", "book", "unitType", "refType", "refId", "title"));
                for (Map<String, Object> r : jdbc.queryForList("""
                        SELECT cu.id, b.title AS book, cu.unit_type, cu.ref_type, cu.ref_id, cu.title
                        FROM content_unit cu LEFT JOIN book b ON b.id = cu.book_id
                        ORDER BY cu.id
                        """)) {
                    rows.add(java.util.Arrays.asList(nz(r.get("id")), nz(r.get("book")), nz(r.get("unit_type")),
                            nz(r.get("ref_type")), nz(r.get("ref_id")), nz(r.get("title"))));
                }
            }
            default -> {
                header.addAll(List.of("herb", "count", "formulaCount", "ratio"));
                for (HerbStatVO h : herbs(100, null)) {
                    rows.add(List.of(h.herb(), String.valueOf(h.count()),
                            String.valueOf(h.formulaCount()), String.valueOf(h.ratio())));
                }
            }
        }

        if ("json".equals(f)) {
            StringBuilder sb = new StringBuilder("{\"kind\":").append(json(k))
                    .append(",\"generatedAt\":").append(json(ISO.format(OffsetDateTime.now())))
                    .append(",\"header\":").append(json(String.join(",", header)))
                    .append(",\"rows\":[");
            for (int i = 0; i < rows.size(); i++) {
                if (i > 0) {
                    sb.append(',');
                }
                List<String> row = rows.get(i);
                Map<String, String> obj = new LinkedHashMap<>();
                for (int j = 0; j < header.size(); j++) {
                    obj.put(header.get(j), j < row.size() ? row.get(j) : "");
                }
                sb.append(toJson(obj));
            }
            sb.append("]}");
            return sb.toString().getBytes(StandardCharsets.UTF_8);
        }

        StringBuilder sb = new StringBuilder("\uFEFF");
        sb.append(String.join(",", header)).append("\r\n");
        for (List<String> row : rows) {
            for (int j = 0; j < row.size(); j++) {
                if (j > 0) {
                    sb.append(',');
                }
                sb.append(csv(row.get(j)));
            }
            sb.append("\r\n");
        }
        return sb.toString().getBytes(StandardCharsets.UTF_8);
    }

    /**
     * 可复现研究包：不落盘，直接返回清单 + 关键统计 + 参数，
     * 前端可一键下载 JSON（含 seed / 生成时间 / 数据版本指纹）。
     */
    public ResearchPackVO researchPack(Map<String, Object> params) {
        Map<String, Object> p = params == null ? Map.of() : params;
        int topN = p.get("topN") instanceof Number nb ? Math.min(Math.max(1, nb.intValue()), 100) : 20;
        String seed = p.get("seed") == null ? String.valueOf(LocalDate.now().toEpochDay()) : String.valueOf(p.get("seed"));

        long formulas = count("SELECT count(*) FROM formula", List.of());
        long cases = count("SELECT count(*) FROM case_record", List.of());
        long quotes = count("SELECT count(*) FROM classic_quote", List.of());
        long units = count("SELECT count(*) FROM content_unit", List.of());
        long vectors = count("SELECT count(*) FROM content_unit WHERE embedding IS NOT NULL", List.of());

        Map<String, Object> summary = new LinkedHashMap<>();
        summary.put("formulas", formulas);
        summary.put("cases", cases);
        summary.put("quotes", quotes);
        summary.put("contentUnits", units);
        summary.put("vectors", vectors);
        summary.put("dataFingerprint", formulas + "-" + cases + "-" + quotes + "-" + units);
        summary.put("totalHerbs", count("SELECT count(DISTINCT herb_name) FROM formula_herb", List.of()));

        List<Map<String, Object>> tables = new ArrayList<>();
        tables.add(table("herbs", "用药频次 Top-N", herbs(topN, null)));
        tables.add(table("syndrome", "证候分布", syndrome(20)));
        TrendVO trend = trend();
        tables.add(table("trend", "经典 / 章节分布", List.of(trend.books(), trend.chapters())));

        List<String> files = List.of(
                "README.md（复现步骤与字段说明）",
                "summary.json（本清单）",
                "herbs.csv（用药频次）",
                "formulas.csv（方剂 + 药味）",
                "quotes.csv（条文原文）",
                "figures/herb-frequency.png（由 herbs.csv 生成）");

        Map<String, Object> paramsOut = new LinkedHashMap<>(p);
        paramsOut.put("topN", topN);
        paramsOut.put("seed", seed);
        paramsOut.put("scope", p.getOrDefault("scope", "all"));

        return new ResearchPackVO("rp_" + UUID.randomUUID().toString().substring(0, 8),
                ISO.format(OffsetDateTime.now()), seed, summary, tables, files, paramsOut);
    }

    // ==================== 工具 ====================

    private Map<String, Object> table(String name, String title, Object data) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("name", name);
        m.put("title", title);
        m.put("rows", data);
        return m;
    }

    private Map<String, Long> group(String sql) {
        Map<String, Long> out = new LinkedHashMap<>();
        try {
            for (Map<String, Object> row : jdbc.queryForList(sql)) {
                String k = str(row.get("k"));
                if (k != null) {
                    out.put(k, num(row.get("c")));
                }
            }
        } catch (Exception e) {
            // 统计失败返回空，不阻塞页面
        }
        return out;
    }

    private List<CountItemVO> toItems(Map<String, Long> map, long total) {
        List<CountItemVO> out = new ArrayList<>();
        for (Map.Entry<String, Long> e : map.entrySet()) {
            out.add(new CountItemVO(e.getKey(), e.getKey(), e.getValue(),
                    total == 0 ? 0 : round((double) e.getValue() / total)));
        }
        return out;
    }

    private long count(String sql, List<Object> args) {
        try {
            Long v = jdbc.queryForObject(sql, Long.class, args.toArray());
            return v == null ? 0 : v;
        } catch (Exception e) {
            return 0;
        }
    }

    private static long num(Object o) {
        return o instanceof Number n ? n.longValue() : 0;
    }

    private static String str(Object o) {
        return o == null ? null : String.valueOf(o);
    }

    /** 导出用：null → 空串（避免 List.of 的 NPE）。 */
    private static String nz(Object o) {
        return o == null ? "" : String.valueOf(o);
    }

    private static double round(double v) {
        return Math.round(v * 1000) / 1000.0;
    }

    private static String csv(String v) {
        if (v == null) {
            return "";
        }
        String s = v.replace("\"", "\"\"");
        return s.contains(",") || s.contains("\"") || s.contains("\n") ? "\"" + s + "\"" : s;
    }

    private static String json(String v) {
        return toJson(v);
    }

    private static String toJson(Object v) {
        if (v == null) {
            return "null";
        }
        if (v instanceof Number || v instanceof Boolean) {
            return String.valueOf(v);
        }
        if (v instanceof Map<?, ?> m) {
            StringBuilder sb = new StringBuilder("{");
            boolean first = true;
            for (Map.Entry<?, ?> e : m.entrySet()) {
                if (!first) {
                    sb.append(',');
                }
                first = false;
                sb.append(toJson(String.valueOf(e.getKey()))).append(':').append(toJson(e.getValue()));
            }
            return sb.append('}').toString();
        }
        if (v instanceof List<?> l) {
            StringBuilder sb = new StringBuilder("[");
            for (int i = 0; i < l.size(); i++) {
                if (i > 0) {
                    sb.append(',');
                }
                sb.append(toJson(l.get(i)));
            }
            return sb.append(']').toString();
        }
        return toJsonString(String.valueOf(v));
    }

    private static String toJsonString(String s) {
        StringBuilder sb = new StringBuilder("\"");
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            switch (c) {
                case '"' -> sb.append("\\\"");
                case '\\' -> sb.append("\\\\");
                case '\n' -> sb.append("\\n");
                case '\r' -> sb.append("\\r");
                case '\t' -> sb.append("\\t");
                default -> {
                    if (c < 0x20) {
                        sb.append(String.format("\\u%04x", (int) c));
                    } else {
                        sb.append(c);
                    }
                }
            }
        }
        return sb.append('"').toString();
    }
}
