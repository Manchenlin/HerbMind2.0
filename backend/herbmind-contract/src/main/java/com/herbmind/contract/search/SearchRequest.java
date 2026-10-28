package com.herbmind.contract.search;

/**
 * 检索请求体 —— POST /api/biz/search/semantic 与 POST /internal/search/recall。
 * q 必填；type / bookId / nodeId / herb 为过滤条件（09 §2、02 §M1 的多维筛选）。
 */
public record SearchRequest(
        String q,
        /** formula / case / quote / all */
        String type,
        String bookId,
        /** 目录节点：章 / 节 / 类（含后代节点下的方剂与医案） */
        String nodeId,
        String herb,
        Integer page,
        Integer size) {
}
