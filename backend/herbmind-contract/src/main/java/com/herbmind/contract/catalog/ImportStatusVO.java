package com.herbmind.contract.catalog;

/**
 * 导入状态 / 解析结果 —— 对应 GET /api/biz/catalog/import/{id}。
 */
public record ImportStatusVO(
        String importId,
        String bookId,
        String title,
        String status,
        String message,
        String createdAt) {
}
