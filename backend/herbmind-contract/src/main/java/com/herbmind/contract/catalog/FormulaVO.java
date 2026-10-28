package com.herbmind.contract.catalog;

import java.util.List;

/**
 * 方剂详情页数据 —— 对应 GET /api/biz/formula/{id}/page。
 */
public record FormulaVO(
        String id,
        String name,
        String pinyin,
        String alias,
        String efficacy,
        String syndrome,
        String sourceText,
        String page,
        String nodeId,
        String nodeTitle,
        String bookId,
        String bookTitle,
        String classicName,
        String chapter,
        List<HerbVO> herbs,
        List<QuoteRefVO> quotes,
        List<CaseBriefVO> cases,
        List<FormulaBriefVO> related) {
}
