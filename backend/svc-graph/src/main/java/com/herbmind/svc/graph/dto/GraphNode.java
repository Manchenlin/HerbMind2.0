package com.herbmind.svc.graph.dto;

import java.util.Map;

/**
 * 子图里的一个节点。
 *
 * @param id     Neo4j elementId（同一张图内唯一，跨库不稳定——对外暴露 ID 需谨慎）
 * @param label  节点类型：Formula / Herb
 * @param name   显示名（Formula 取 name，Herb 取 name）
 * @param props  其余标量属性（Formula：syndrome / page），无则不输出（yml 配了 non_null）
 */
public record GraphNode(String id, String label, String name, Map<String, Object> props) {
}
