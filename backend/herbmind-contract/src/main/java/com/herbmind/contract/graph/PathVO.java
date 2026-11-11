package com.herbmind.contract.graph;

import java.util.List;

/**
 * 两实体之间的路径 —— 09 契约 §15.4，对应 {@code GET /api/biz/graph/path}。
 *
 * @param found       false **不是错误**：表示两个实体在 maxHops 跳内没有关联，前端正常展示「无关联」
 * @param paths       按 length 升序，最多 limit 条
 * @param explanation 人类可读说明，如「经共享药味『桂枝』相连（2 跳）」
 */
public record PathVO(
        boolean found,
        List<GraphPathVO> paths,
        String explanation) {

    /** 一条路径。 */
    public record GraphPathVO(
            List<GraphNodeVO> nodes,
            List<GraphEdgeVO> edges,
            int length) {
    }
}
