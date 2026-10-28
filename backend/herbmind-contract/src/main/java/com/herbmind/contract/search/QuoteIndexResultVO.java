package com.herbmind.contract.search;

import java.util.List;

/**
 * 条文反向索引结果（GET /api/biz/search/quote-index）。
 */
public record QuoteIndexResultVO(
        List<QuoteIndexItemVO> list,
        long total,
        int page,
        int size) {
}
