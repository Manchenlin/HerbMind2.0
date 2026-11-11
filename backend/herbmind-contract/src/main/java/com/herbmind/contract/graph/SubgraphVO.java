package com.herbmind.contract.graph;

import java.util.List;

/**
 * 子图 —— 09 契约 §15.2，对应 {@code GET /api/biz/graph/subgraph}。
 *
 * <p>供前端力导向渲染；边两端的节点必然都在 {@code nodes} 里，前端不需要做悬空边容错。
 *
 * @param nodes     子图节点
 * @param edges     子图边
 * @param stats     规模统计，便于前端决定是否开启力导向布局
 * @param truncated true = 达到 limit 被截断
 */
public record SubgraphVO(
        List<GraphNodeVO> nodes,
        List<GraphEdgeVO> edges,
        Stats stats,
        boolean truncated) {

    /** 规模统计。 */
    public record Stats(int nodeCount, int edgeCount) {
    }
}
