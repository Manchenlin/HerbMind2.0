package com.herbmind.contract.search;

import java.util.List;

import com.herbmind.contract.catalog.LinkVO;

/**
 * 条文反向索引条目：一条原文 + 引用它的方剂 / 医案。
 */
public record QuoteIndexItemVO(
        String quoteId,
        String classicName,
        String articleNo,
        String text,
        String page,
        List<LinkVO> formulas,
        List<LinkVO> cases) {
}
