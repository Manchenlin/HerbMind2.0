package com.herbmind.svc.graph.dto;

import java.util.List;

/**
 * 邻居子图（对应契约 `/internal/graph/neighbors`）。
 *
 * internal 接口直接返回本 DTO（**不包 R**，与 svc-catalog 一致）：
 * 统一外壳由 BFF 负责，避免每个 svc 各包一层导致前端要拆两次。
 *
 * @param center    中心节点
 * @param nodes     全部节点（含 center，已去重）
 * @param edges     全部关系（已去重）
 * @param hops      实际生效的跳数（入参会被夹到 1..3）
 * @param truncated true = 结果被 limit 截断，前端应提示"图太大，请缩小范围"
 */
public record Subgraph(GraphNode center, List<GraphNode> nodes, List<GraphEdge> edges,
                       int hops, boolean truncated) {
}
