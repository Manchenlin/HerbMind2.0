package com.herbmind.svc.graph.dto;

import java.util.Map;

/**
 * 子图里的一个节点。
 *
 * @param id    业务 ID：方剂 {@code f_1}、药味 {@code h_麻黄}（**不是 Neo4j elementId**，
 *              elementId 重建库/重启就会变，不能给前端收藏或分享用）
 * @param label 节点类型：Formula / Herb
 * @param name  显示名（Formula 取 name，Herb 取 name）
 * @param props 其余标量属性（Formula：syndrome / page；Herb：空对象），无值不输出
 */
public record GraphNode(String id, String label, String name, Map<String, Object> props) {
}
