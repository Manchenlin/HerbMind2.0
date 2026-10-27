package com.herbmind.svc.graph.dto;

import java.util.Map;

/**
 * 子图里的一条关系。
 *
 * @param from   起点节点 ID（elementId）
 * @param to     终点节点 ID（elementId）
 * @param rel    关系类型：目前只有 COMPOSED_OF
 * @param props  关系属性（COMPOSED_OF：dose / unit / role，即君臣佐使与剂量）
 */
public record GraphEdge(String from, String to, String rel, Map<String, Object> props) {
}
