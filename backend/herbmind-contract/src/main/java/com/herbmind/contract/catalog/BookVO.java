package com.herbmind.contract.catalog;

/**
 * 语料（书架）VO —— 对应 09 契约 §4 /api/biz/catalog/books。
 * 字段全部 camelCase；时间为 ISO 8601 字符串。
 */
public record BookVO(
        String id,
        String title,
        String bookType,
        String bookTypeLabel,
        String author,
        String dynasty,
        String edition,
        String sourceLicense,
        String ingestStatus,
        String statusLabel,
        String createdAt,
        long unitCount,
        long nodeCount,
        long formulaCount,
        long caseCount) {
}
