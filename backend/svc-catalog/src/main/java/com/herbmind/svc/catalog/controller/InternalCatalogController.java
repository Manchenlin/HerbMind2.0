package com.herbmind.svc.catalog.controller;

import java.util.List;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import com.herbmind.contract.catalog.BookTreeNode;
import com.herbmind.svc.catalog.service.BookNodeService;

/**
 * 内部接口（/internal/**，不进网关）。
 * 返回**裸 DTO**（不包 R），由 BFF 统一包 R&lt;T&gt; 给前端。
 */
@RestController
@RequestMapping("/internal/catalog")
public class InternalCatalogController {

    private final BookNodeService service;

    public InternalCatalogController(BookNodeService service) {
        this.service = service;
    }

    @GetMapping("/tree")
    public List<BookTreeNode> tree(@RequestParam(value = "bookId", required = false, defaultValue = "fz") String bookId) {
        return service.tree(bookId);
    }

    @GetMapping("/node/{id}")
    public BookTreeNode node(@PathVariable("id") String id) {
        return service.node(id);
    }
}
