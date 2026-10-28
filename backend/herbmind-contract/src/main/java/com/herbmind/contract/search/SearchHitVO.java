package com.herbmind.contract.search;

import java.util.List;
import java.util.Map;

/**
 * 一条检索命中。id = content_unit.id（条文命中时为 classic_quote.id + 条号）。
 * matchedBy 说明命中的召回腿：vector / fulltext / fuzzy / quote。
 * section / chapter 来自 content_unit.meta_jsonb（真实数据里 section 比 chapter 更细）。
 */
public record SearchHitVO(
        String id,
        /** formula / case / quote */
        String refType,
        String refId,
        String title,
        String snippet,
        double score,
        String bookId,
        String bookTitle,
        String classic,
        String chapter,
        String section,
        String page,
        List<String> herbs,
        List<String> matchedBy,
        Map<String, Object> meta) {
}
