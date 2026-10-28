package com.herbmind.bff.catalog;

import java.util.List;

import com.herbmind.contract.catalog.BookVO;
import com.herbmind.contract.catalog.CatalogStatsVO;
import com.herbmind.contract.catalog.FormulaVO;
import com.herbmind.contract.catalog.GraphPreviewVO;
import com.herbmind.contract.search.SearchHitVO;

/**
 * 首页聚合结果（GET /api/biz/home）。
 *
 * 17 号手册 A4 要求聚合 **catalog + search + graph 预览**：
 *   stats / books / today  ← catalog
 *   hotHits                ← search（首页「大家都在查」区块）
 *   graph                  ← 图谱预览（内容域轻量版，svc-graph 就绪后可切）
 *
 * degraded 列出本次降级的分区（如 svc-search 未启动）——
 * 首页在任何一个 svc 挂掉时仍要能渲染，只是对应区块留空。
 */
public record HomeVO(
        CatalogStatsVO stats,
        List<BookVO> books,
        FormulaVO today,
        GraphPreviewVO graph,
        String graphSource,
        List<String> hotKeywords,
        List<SearchHitVO> hotHits,
        List<String> degraded) {
}
