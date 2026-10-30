package com.herbmind.svc.graph.dto;

import java.util.List;

/**
 * 相似度地图坐标（09 契约 §15.5，对应 `/internal/graph/map`）。
 *
 * 坐标由**服务端确定性计算**：同一 {@code version} 反复请求必须给出同一张图，
 * 否则每次刷新图形乱跳，无法用于讲解与截图。前端只画点、不自行布局。
 *
 * @param metric    距离口径，一期只允许 composition（药味 Jaccard），不提供"功效相似"这类推断口径
 * @param points    点集，x/y 已归一化到 0~1
 * @param version   计算版本（metric + 数据指纹），同版本必须可复现
 * @param truncated 是否因 limit 截断
 */
public record GraphMap(String metric, List<Point> points, String version, boolean truncated) {

    /**
     * 一个点。
     *
     * @param cluster 分组标签（c1、c2…）：按药味 Jaccard 由 0.5 起逐级升档切出的确定性分组
     *                （同色 = 药味重合度高的一群，簇过大会升档再拆），
     *                仅供前端配色，**不代表证型、功效或任何医学分类**
     */
    public record Point(String id, String label, String name, double x, double y, String cluster) {
    }
}
