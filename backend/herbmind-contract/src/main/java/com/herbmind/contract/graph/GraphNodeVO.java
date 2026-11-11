package com.herbmind.contract.graph;

import java.util.Map;

/**
 * 图谱节点 —— 09 契约 §15 各端点返回的公共结构。
 *
 * <p>字段与 svc-graph 的 {@code GraphNode} 逐字一致，BFF 只做透传不做转换：
 * <ul>
 *   <li>{@code id}：业务 ID（方剂 {@code f_1}、药味 {@code h_麻黄}），<b>不是</b> Neo4j elementId
 *       —— elementId 重建库/重启就会变，不能给前端收藏或分享用；</li>
 *   <li>{@code label}：节点类型，当前只有 {@code Formula} / {@code Herb}；</li>
 *   <li>{@code props}：其余标量属性（Formula 有 syndrome / page，Herb 为空对象），无值不输出。</li>
 * </ul>
 */
public record GraphNodeVO(
        String id,
        String label,
        String name,
        Map<String, Object> props) {
}
