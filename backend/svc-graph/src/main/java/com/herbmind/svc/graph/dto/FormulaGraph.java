package com.herbmind.svc.graph.dto;

import java.util.List;

/**
 * 方心子图（09 契约 §15.3，对应 `/internal/graph/formula/{id}`）。
 *
 * 数据来源分工：中心方剂与药味顺序取 **PG**（formula / formula_herb，seq 只有 PG 有），
 * {@code relatedFormulas} 用**药味集合 Jaccard** 计算（确定性规则，不是模型推断）。
 *
 * @param center          中心方剂
 * @param herbs           药味，按库内 seq 升序
 * @param herbsIncomplete true = 该方在库内药味缺失或含疑似解析残留（脏药名），前端需提示
 * @param relatedFormulas 药味交集最大的成方，按 Jaccard 降序、最多 5 条
 * @param notice          免责声明（不推断功效、不给处方建议）
 */
public record FormulaGraph(Center center, List<Herb> herbs, boolean herbsIncomplete,
                           List<RelatedFormula> relatedFormulas, String notice) {

    /**
     * 中心方剂（syndromeText 为语料原文摘录）。
     *
     * alias / page 在库里大量为空（[实核 2026-10-28] page 245/245 为空、alias 仅 86/245 有值），
     * 这里仍按契约把字段输出出来（空串或 null），不让前端区分"没这个字段"和"库内没记"。
     */
    @com.fasterxml.jackson.annotation.JsonInclude(com.fasterxml.jackson.annotation.JsonInclude.Include.ALWAYS)
    public record Center(String id, String name, String alias, String syndromeText, String page) {
    }

    /**
     * 药味一项。dose/unit/role 多数为空（[实核 2026-10-28] 1315 条药味里只有 69 条有剂量），
     * 所以这里显式允许 null 输出（契约 §15.3 示例就是 {@code "dose":null}），
     * 不受本项目全局 non_null 配置影响。
     */
    @com.fasterxml.jackson.annotation.JsonInclude(com.fasterxml.jackson.annotation.JsonInclude.Include.ALWAYS)
    public record Herb(String id, String name, int seq, String dose, String unit, String role) {
    }

    /**
     * 关联方。
     *
     * @param sharedHerbs 交集药味（按药名排序，便于前端稳定展示）
     * @param jaccard     |A∩B| / |A∪B|，保留 4 位小数
     */
    public record RelatedFormula(String id, String name, List<String> sharedHerbs, double jaccard) {
    }
}
