package com.herbmind.svc.graph.dto;

import java.util.List;

/**
 * 子图（09 契约 §15.2，对应 `/internal/graph/subgraph`）。
 *
 * internal 接口直接返回本 DTO（**不包 R**，与 svc-catalog 同一约定）：
 * 统一外壳由 BFF 负责，避免每个 svc 各包一层导致前端要拆两次。
 *
 * @param nodes     子图节点（id 为业务 ID：f_* / h_*）
 * @param edges     子图边（两端都必定出现在 nodes 里）
 * @param stats     规模，便于前端决定是否开启力导向布局
 * @param truncated true = 达到 limit 被截断，前端应提示"图太大，请缩小范围"
 */
public record Subgraph(List<GraphNode> nodes, List<GraphEdge> edges, Stats stats, boolean truncated) {

    /** 规模统计。 */
    public record Stats(int nodeCount, int edgeCount) {
    }
}
