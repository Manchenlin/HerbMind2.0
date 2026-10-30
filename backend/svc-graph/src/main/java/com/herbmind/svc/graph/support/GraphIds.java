package com.herbmind.svc.graph.support;

/**
 * 对外 ID 口径（09 契约 §15 硬约定）：方剂 {@code f_*}、药味 {@code h_*}。
 *
 * **禁止直接暴露 Neo4j 的 elementId**：重建库或重启后它会变，前端收藏、URL 分享、缓存都会失效。
 * 这里的换算全部是纯函数，便于单测。
 *
 * [实核 2026-10-28] PG 里 245 条 formula.id 全部已是 {@code f_*} 形态、Neo4j 由
 * {@code build_graph.py} 以同一 id 建点；Herb 节点只有 name 一个属性，所以 {@code h_} 前缀是拼出来的。
 */
public final class GraphIds {

    public static final String FORMULA_PREFIX = "f_";
    public static final String HERB_PREFIX = "h_";

    private GraphIds() {
    }

    /** 裸 id / 已带前缀的 id → {@code f_*}。空串返回 null，由调用方报 4000。 */
    public static String formulaId(String raw) {
        if (raw == null) {
            return null;
        }
        String s = raw.trim();
        if (s.isEmpty()) {
            return null;
        }
        return s.startsWith(FORMULA_PREFIX) ? s : FORMULA_PREFIX + s;
    }

    /** 药名 → {@code h_药名}。 */
    public static String herbId(String name) {
        if (name == null) {
            return null;
        }
        String s = name.trim();
        return s.isEmpty() ? null : HERB_PREFIX + s;
    }

    public static boolean isFormulaId(String s) {
        return s != null && s.startsWith(FORMULA_PREFIX);
    }

    public static boolean isHerbId(String s) {
        return s != null && s.startsWith(HERB_PREFIX);
    }

    /** {@code f_12} → {@code 12}；不带前缀或是非数字后缀时返回原串。 */
    public static String stripFormula(String s) {
        return isFormulaId(s) ? s.substring(FORMULA_PREFIX.length()) : s;
    }

    /** {@code h_麻黄} → {@code 麻黄}；不带前缀时返回原串。 */
    public static String stripHerb(String s) {
        return isHerbId(s) ? s.substring(HERB_PREFIX.length()) : s;
    }

    /**
     * 按数字后缀排序：避免 {@code f_10} 排在 {@code f_9} 前面的字典序陷阱。
     * 非数字后缀（如 h_麻黄）退回字符串比较。
     */
    public static int compareById(String a, String b) {
        String left = a == null ? "" : a;
        String right = b == null ? "" : b;
        int na = numericSuffix(left);
        int nb = numericSuffix(right);
        if (na >= 0 && nb >= 0 && na != nb) {
            return Integer.compare(na, nb);
        }
        return left.compareTo(right);
    }

    private static int numericSuffix(String s) {
        int idx = s.lastIndexOf('_');
        if (idx < 0 || idx == s.length() - 1) {
            return -1;
        }
        String tail = s.substring(idx + 1);
        try {
            return Integer.parseInt(tail);
        } catch (NumberFormatException e) {
            return -1;
        }
    }
}
