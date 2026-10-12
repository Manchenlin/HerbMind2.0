package com.herbmind.bff.controller;

import java.util.List;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import com.herbmind.common.R;
import com.herbmind.contract.catalog.BookTreeNode;
import com.herbmind.contract.catalog.CatalogClient;

/**
 * BFF：典籍目录树（域1 的端点）。
 * 前端只调 /api/biz/**；BFF 经 Feign 取 /internal/catalog/tree，包成 R&lt;T&gt;。
 */
@RestController
@RequestMapping("/api/biz")
public class LibraryController {

    private final CatalogClient catalog;

    public LibraryController(CatalogClient catalog) {
        this.catalog = catalog;
    }

    @GetMapping("/library/tree")
    public R<List<BookTreeNode>> tree(
            @RequestParam(value = "bookId", required = false, defaultValue = "fz") String bookId) {
        return R.ok(catalog.tree(bookId));
    }
}
