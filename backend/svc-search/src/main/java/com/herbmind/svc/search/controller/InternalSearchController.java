package com.herbmind.svc.search.controller;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import com.herbmind.contract.search.FacetsVO;
import com.herbmind.contract.search.QuoteIndexResultVO;
import com.herbmind.contract.search.SearchRequest;
import com.herbmind.contract.search.SearchResultVO;
import com.herbmind.svc.search.service.QuoteIndexService;
import com.herbmind.svc.search.service.SearchService;

/**
 * 内部检索接口（/internal/search/**，不进网关）。
 * 返回裸 DTO，由 BFF 统一包 R。
 */
@RestController
@RequestMapping("/internal/search")
public class InternalSearchController {

    private final SearchService searchService;
    private final QuoteIndexService quoteIndexService;

    public InternalSearchController(SearchService searchService, QuoteIndexService quoteIndexService) {
        this.searchService = searchService;
        this.quoteIndexService = quoteIndexService;
    }

    /** 多维 / 关键词检索（分面）。 */
    @GetMapping
    public SearchResultVO search(
            @RequestParam(value = "q", required = false, defaultValue = "") String q,
            @RequestParam(value = "type", required = false) String type,
            @RequestParam(value = "bookId", required = false) String bookId,
            @RequestParam(value = "nodeId", required = false) String nodeId,
            @RequestParam(value = "herb", required = false) String herb,
            @RequestParam(value = "page", required = false, defaultValue = "1") int page,
            @RequestParam(value = "size", required = false, defaultValue = "10") int size) {
        return searchService.search(new SearchRequest(q, type, bookId, nodeId, herb, page, size));
    }

    /** 语义检索（混合召回）。 */
    @PostMapping("/semantic")
    public SearchResultVO semantic(@RequestBody SearchRequest request) {
        return searchService.search(request);
    }

    /** 向量 + 全文混合召回（供 Agent 调用，语义与 semantic 一致）。 */
    @PostMapping("/recall")
    public SearchResultVO recall(@RequestBody SearchRequest request) {
        return searchService.search(request);
    }

    /** 条文反向索引。 */
    @GetMapping("/quote-index")
    public QuoteIndexResultVO quoteIndex(
            @RequestParam(value = "q", required = false, defaultValue = "") String q,
            @RequestParam(value = "bookId", required = false) String bookId,
            @RequestParam(value = "page", required = false, defaultValue = "1") int page,
            @RequestParam(value = "size", required = false, defaultValue = "20") int size) {
        return quoteIndexService.quoteIndex(q, bookId, page, size);
    }

    /** 分面统计。 */
    @GetMapping("/facets")
    public FacetsVO facets(
            @RequestParam(value = "q", required = false, defaultValue = "") String q,
            @RequestParam(value = "bookId", required = false) String bookId) {
        return searchService.facets(q, bookId);
    }
}
