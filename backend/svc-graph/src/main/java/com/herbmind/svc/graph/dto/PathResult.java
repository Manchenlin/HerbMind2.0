package com.herbmind.svc.graph.dto;

import java.util.List;

/**
 * 两实体之间的路径（09 契约 §15.4，对应 `/internal/graph/path`）。
 *
 * @param found       false **不是错误**，前端显示"两实体之间最多 N 跳内无关联"
 * @param paths       按 length 升序、最多 limit 条
 * @param explanation 人类可读说明，如「经共享药味「桂枝」相连（2 跳）」
 */
public record PathResult(boolean found, List<GraphPath> paths, String explanation) {

    /** 一条路径。 */
    public record GraphPath(List<GraphNode> nodes, List<GraphEdge> edges, int length) {
    }
}
