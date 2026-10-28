package com.herbmind.contract.catalog;

/**
 * 全库统计（首页数字卡片 / 治理总览用）。
 */
public record CatalogStatsVO(
        long books,
        long nodes,
        long formulas,
        long cases,
        long quotes,
        long vectors) {
}
