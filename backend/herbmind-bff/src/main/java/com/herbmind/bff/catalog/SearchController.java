package com.herbmind.bff.catalog;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import com.herbmind.common.R;
import com.herbmind.contract.search.FacetsVO;
import com.herbmind.contract.search.QuoteIndexResultVO;
import com.herbmind.contract.search.SearchClient;
import com.herbmind.contract.search.SearchRequest;
import com.herbmind.contract.search.SearchResultVO;

/**
 * 检索 BFF（多维检索 / 语义检索 / 条文反向索引 / 分面）。
 */
@RestController
@RequestMapping("/api/biz")
public class SearchController {

    private final SearchClient search;

    public SearchController(SearchClient search) {
        this.search = search;
    }

    @GetMapping("/search")
    public R<SearchResultVO> search(
            @RequestParam(value = "q", required = false, defaultValue = "") String q,
            @RequestParam(value = "type", required = false) String type,
            @RequestParam(value = "bookId", required = false) String bookId,
            @RequestParam(value = "nodeId", required = false) String nodeId,
            @RequestParam(value = "herb", required = false) String herb,
            @RequestParam(value = "page", required = false, defaultValue = "1") int page,
            @RequestParam(value = "size", required = false, defaultValue = "10") int size) {
        return R.ok(search.search(nz(q), nz(type), nz(bookId), nz(nodeId), nz(herb), page, size));
    }

    @PostMapping("/search/semantic")
    public R<SearchResultVO> semantic(@RequestBody SearchRequest request) {
        return R.ok(search.semantic(request));
    }

    @GetMapping("/search/quote-index")
    public R<QuoteIndexResultVO> quoteIndex(
            @RequestParam(value = "q", required = false, defaultValue = "") String q,
            @RequestParam(value = "bookId", required = false) String bookId,
            @RequestParam(value = "page", required = false, defaultValue = "1") int page,
            @RequestParam(value = "size", required = false, defaultValue = "20") int size) {
        return R.ok(search.quoteIndex(nz(q), nz(bookId), page, size));
    }

    @GetMapping("/search/facets")
    public R<FacetsVO> facets(
            @RequestParam(value = "q", required = false, defaultValue = "") String q,
            @RequestParam(value = "bookId", required = false) String bookId) {
        return R.ok(search.facets(nz(q), nz(bookId)));
    }

    /** Feign 的查询参数传 null 会拼出空占位，统一转成空串，由 svc 侧按「空 = 不过滤」处理。 */
    private static String nz(String s) {
        return s == null ? "" : s;
    }
}
