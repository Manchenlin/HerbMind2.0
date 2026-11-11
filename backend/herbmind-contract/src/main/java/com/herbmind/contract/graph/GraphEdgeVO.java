package com.herbmind.contract.graph;

import java.util.Map;

/**
 * 图谱中的一条关系 —— 09 契约 §15 各端点返回的公共结构。
 *
 * @param source 起点节点业务 ID（{@code f_*} / {@code h_*}）
 * @param target 终点节点业务 ID
 * @param rel    关系类型，当前只有 {@code COMPOSED_OF}（方剂 → 药味）
 * @param props  关系属性（{@code COMPOSED_OF} 下为 dose / unit / role，即君臣佐使与剂量），无则不是输出
 */
public record GraphEdgeVO(
        String source,
        String target,
        String rel,
        Map<String, Object> props) {
}
