package com.herbmind.contract.search;

import java.util.List;

/**
 * 检索结果：分页 + 分面。
 * mode = hybrid（向量腿可用）/ fulltext（无 embedding 服务时的降级）/ fuzzy（pg_jieba 未装时的兜底）。
 */
public record SearchResultVO(
        List<SearchHitVO> list,
        long total,
        int page,
        int size,
        String mode,
        long tookMs,
        FacetsVO facets) {
}
