package com.herbmind.svc.graph.dto;

import java.util.Map;

/**
 * 子图里的一条关系。
 *
 * @param source 起点节点 ID（业务 ID：f_* / h_*）
 * @param target 终点节点 ID
 * @param rel    关系类型：目前只有 COMPOSED_OF
 * @param props  关系属性（COMPOSED_OF：dose / unit / role，即君臣佐使与剂量），无则不输出
 */
public record GraphEdge(String source, String target, String rel, Map<String, Object> props) {
}
