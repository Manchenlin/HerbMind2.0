package com.herbmind.contract.insight;

import java.util.List;

/**
 * 经典 / 章节分布（GET /api/biz/insight/trend）。
 */
public record TrendVO(
        List<CountItemVO> books,
        List<CountItemVO> chapters,
        long totalUnits,
        long totalFormulas,
        long totalCases,
        long totalQuotes) {
}
