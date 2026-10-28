package com.herbmind.contract.catalog;

import java.util.List;

/**
 * 条文详情页数据 —— 对应 GET /api/biz/quote/{id}/page。
 * items 为按编号拆出的逐条原文；formulas / cases 为引用本条的方剂与医案（反向索引）。
 */
public record QuoteVO(
        String id,
        String articleNo,
        String classicId,
        String classicName,
        String bookId,
        String bookTitle,
        String content,
        String plainText,
        String page,
        String label,
        List<QuoteItemVO> items,
        List<LinkVO> formulas,
        List<LinkVO> cases) {
}
