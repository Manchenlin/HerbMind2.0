package com.herbmind.contract.search;

import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestParam;

/**
 * svc-search 内部契约（:8083）。返回裸 DTO，由 BFF 包 R。
 */
@FeignClient(name = "svc-search", path = "/internal/search",
        url = "${herbmind.svc-search-url:http://localhost:8083}")
public interface SearchClient {

    @GetMapping
    SearchResultVO search(@RequestParam("q") String q,
                          @RequestParam(value = "type", required = false) String type,
                          @RequestParam(value = "bookId", required = false) String bookId,
                          @RequestParam(value = "nodeId", required = false) String nodeId,
                          @RequestParam(value = "herb", required = false) String herb,
                          @RequestParam(value = "page", defaultValue = "1") int page,
                          @RequestParam(value = "size", defaultValue = "10") int size);

    @PostMapping("/semantic")
    SearchResultVO semantic(@RequestBody SearchRequest request);

    @PostMapping("/recall")
    SearchResultVO recall(@RequestBody SearchRequest request);

    @GetMapping("/quote-index")
    QuoteIndexResultVO quoteIndex(@RequestParam(value = "q", required = false) String q,
                                  @RequestParam(value = "bookId", required = false) String bookId,
                                  @RequestParam(value = "page", defaultValue = "1") int page,
                                  @RequestParam(value = "size", defaultValue = "20") int size);

    @GetMapping("/facets")
    FacetsVO facets(@RequestParam(value = "q", required = false) String q,
                    @RequestParam(value = "bookId", required = false) String bookId);
}
