package com.herbmind.contract.graph;

import java.util.List;

/**
 * 方心子图 —— 09 契约 §15.3，对应 {@code GET /api/biz/graph/formula/{id}}。
 *
 * <p>数据来源分工：中心方剂与药味顺序号（{@code seq}）取自 **PG**（formula / formula_herb）；
 * {@code relatedFormulas} 由**药味集合 Jaccard** 计算，是确定性规则，不是模型推断。
 *
 * <p><b>关于 null 字段</b>：BFF 全局配置 {@code default-property-inclusion: non_null} 会把值为 null
 * 的字段整条省略（不是输出 {@code null}）。所以前端取 {@code alias} / {@code syndromeText} /
 * {@code dose} / {@code unit} / {@code role} / {@code page} 时一律用 {@code ?? ''} 兜底，
 * 不要假设字段一定出现在 JSON 里。契约 §15.3 示例写的是 {@code "dose": null}，语义上等价。
 *
 * @param center          中心方剂
 * @param herbs           药味，按库内 seq 升序
 * @param herbsIncomplete true = 该方在库内药味缺失或含疑似解析残留（脏药名），前端需提示
 * @param relatedFormulas 药味交集最大的成方，按 Jaccard 降序、最多 5 条
 * @param notice          免责声明（不推断功效、不给处方建议）
 */
public record FormulaGraphVO(
        Center center,
        List<Herb> herbs,
        boolean herbsIncomplete,
        List<RelatedFormula> relatedFormulas,
        String notice) {

    /**
     * 中心方剂（{@code syndromeText} 为语料原文摘录）。
     *
     * <p>{@code alias} / {@code page} 在库里大量为空（page 245/245 为空、alias 仅 86/245 有值），
     * 前端不要把空值当异常。
     */
    public record Center(
            String id,
            String name,
            String alias,
            String syndromeText,
            String page) {
    }

    /**
     * 药味一项。
     *
     * <p>{@code dose} / {@code unit} / {@code role} 多数为空（1315 条药味里只有 69 条有剂量）。
     * <b>剂量是字符串</b>（后端为避浮点误差已转字符串），前端不要做数值转换。
     */
    public record Herb(
            String id,
            String name,
            int seq,
            String dose,
            String unit,
            String role) {
    }

    /**
     * 组成相近的成方。
     *
     * <p><b>口径提醒（设计红线）</b>：{@code jaccard} 只表示药味集合的重合度，
     * 页面上只能写「组成相近 ≠ 同一方」，不得表述为「同类方」「功效相近」。
     *
     * @param sharedHerbs 交集药味（按药名排序，便于前端稳定展示）
     * @param jaccard     |A∩B| / |A∪B|，保留 4 位小数
     */
    public record RelatedFormula(
            String id,
            String name,
            List<String> sharedHerbs,
            double jaccard) {
    }
}
