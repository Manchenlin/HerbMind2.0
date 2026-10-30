package com.herbmind.svc.graph.repo;

import java.math.BigDecimal;
import java.util.List;

import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

/**
 * PG 只读查询：方剂元数据 + 药味明细（含顺序 seq）。
 *
 * **只做 SELECT**，且数据源在 {@link com.herbmind.svc.graph.config.PgConfig} 里已把会话设成
 * {@code default_transaction_read_only=on}，写语句会在 PG 侧直接失败。
 *
 * 为什么整表取回来在内存里算，而不是把 Jaccard 写成一坨 SQL：
 * 1. 规模极小（[实核 2026-10-28] formula=245、formula_herb=1315 行），全量拉取 < 10ms；
 * 2. 药味比对、脏药名判定、地图布局都要用同一份药味集合，走内存只读一次库；
 * 3. 纯 Java 可单测，SQL 里的窗口/数组聚合只能靠连库才能验证。
 */
@Repository
public class CompositionRepository {

    private static final String SQL_FORMULAS =
            "SELECT id, name, alias, syndrome_text, page, node_id FROM formula";

    private static final String SQL_HERB_ROWS =
            "SELECT formula_id, herb_name, seq, dose, unit, role "
                    + "FROM formula_herb ORDER BY formula_id, seq, herb_name";

    private final JdbcTemplate jdbc;

    public CompositionRepository(@Qualifier("pgJdbcTemplate") JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    /** 全部方剂（245 行）。 */
    public List<FormulaRow> formulas() {
        return jdbc.query(SQL_FORMULAS, (rs, i) -> new FormulaRow(
                rs.getString("id"),
                rs.getString("name"),
                rs.getString("alias"),
                rs.getString("syndrome_text"),
                rs.getString("page"),
                rs.getString("node_id")));
    }

    /** 全部药味行（1315 行），已按 formula_id / seq 排序。 */
    public List<HerbRow> herbRows() {
        return jdbc.query(SQL_HERB_ROWS, (rs, i) -> new HerbRow(
                rs.getString("formula_id"),
                rs.getString("herb_name"),
                rs.getInt("seq"),
                // dose 是 NUMERIC：统一用字符串传出去（避免 double 出现 9.000000000000002），
                // 并去掉尾随零 —— PgJDBC 的 getString 会把 4 读成 "4.0"，前端要显示"4 两"
                plainNumber(rs.getBigDecimal("dose")),
                rs.getString("unit"),
                rs.getString("role")));
    }

    /**
     * 某目录节点及其所有子孙节点 ID（/map 的 nodeId 筛选用：点某章 → 该章下全部方剂）。
     * 递归 CTE 只读 book_node，深度有限，245 方规模下开销可忽略。
     */
    public List<String> descendantNodeIds(String nodeId) {
        return jdbc.queryForList(
                "WITH RECURSIVE sub AS ("
                        + "  SELECT id FROM book_node WHERE id = ? "
                        + "  UNION ALL "
                        + "  SELECT n.id FROM book_node n JOIN sub s ON n.parent_id = s.id"
                        + ") SELECT id FROM sub",
                String.class, nodeId);
    }

    /** formula 表一行（id 已是 f_* 形态）。 */
    public record FormulaRow(String id, String name, String alias, String syndromeText,
                             String page, String nodeId) {
    }

    private static String plainNumber(BigDecimal v) {
        return v == null ? null : v.stripTrailingZeros().toPlainString();
    }

    /** formula_herb 表一行。dose 为 null 表示库内没记剂量。 */
    public record HerbRow(String formulaId, String herbName, int seq, String dose,
                          String unit, String role) {
    }
}
