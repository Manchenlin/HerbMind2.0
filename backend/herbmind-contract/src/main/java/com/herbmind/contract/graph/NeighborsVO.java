package com.herbmind.contract.graph;

import java.util.List;

/**
 * 单实体邻居 —— 09 契约 §15.1，对应 {@code GET /api/biz/graph/neighbors}。
 *
 * @param center    中心节点
 * @param nodes     邻居节点，**不含 center**；按 label 再按 name 升序
 * @param edges     邻居与 center 之间的边（只保留一端是 center 的）
 * @param truncated true = 邻居数超过 limit 被截断，前端应提示「图太大，请缩小范围」
 */
public record NeighborsVO(
        GraphNodeVO center,
        List<GraphNodeVO> nodes,
        List<GraphEdgeVO> edges,
        boolean truncated) {
}
