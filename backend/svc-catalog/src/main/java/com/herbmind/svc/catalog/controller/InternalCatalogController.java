package com.herbmind.svc.catalog.controller;

import java.util.List;
import java.util.Map;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import com.herbmind.contract.catalog.BookTreeNode;
import com.herbmind.contract.catalog.BookVO;
import com.herbmind.contract.catalog.CatalogStatsVO;
import com.herbmind.contract.catalog.CaseVO;
import com.herbmind.contract.catalog.FormulaBriefVO;
import com.herbmind.contract.catalog.FormulaVO;
import com.herbmind.contract.catalog.GraphPreviewVO;
import com.herbmind.contract.catalog.ImportRequest;
import com.herbmind.contract.catalog.ImportStatusVO;
import com.herbmind.contract.catalog.NodeDetailVO;
import com.herbmind.contract.catalog.QuoteListVO;
import com.herbmind.contract.catalog.QuoteVO;
import com.herbmind.svc.catalog.mapper.BookMapper;
import com.herbmind.svc.catalog.service.CatalogService;

/**
 * 内部接口（/internal/**，不进网关）。
 * 返回**裸 DTO**（不包 R），由 BFF 统一包 R&lt;T&gt; 给前端。
 */
@RestController
@RequestMapping("/internal/catalog")
public class InternalCatalogController {

    private final CatalogService service;
    private final BookMapper bookMapper;

    public InternalCatalogController(CatalogService service, BookMapper bookMapper) {
        this.service = service;
        this.bookMapper = bookMapper;
    }

    // ---------- 语料 / 书架 ----------

    @GetMapping("/books")
    public List<BookVO> books() {
        return service.books();
    }

    @PostMapping("/import")
    public ImportStatusVO importBook(@RequestBody ImportRequest request) {
        return service.importBook(request);
    }

    @GetMapping("/import/{id}")
    public ImportStatusVO importStatus(@PathVariable("id") String id) {
        return service.importStatus(id);
    }

    // ---------- 目录 ----------

    @GetMapping("/tree")
    public List<BookTreeNode> tree(
            @RequestParam(value = "bookId", required = false, defaultValue = "bk_1") String bookId) {
        return service.tree(bookId);
    }

    @GetMapping("/node/{id}")
    public BookTreeNode node(@PathVariable("id") String id) {
        return service.nodeDetail(id).node();
    }

    @GetMapping("/node/{id}/detail")
    public NodeDetailVO nodeDetail(@PathVariable("id") String id) {
        return service.nodeDetail(id);
    }

    // ---------- 方剂 / 医案 / 条文 ----------

    @GetMapping("/formula/{id}")
    public FormulaVO formula(@PathVariable("id") String id) {
        return service.formula(id);
    }

    @GetMapping("/case/{id}")
    public CaseVO caseRecord(@PathVariable("id") String id) {
        return service.caseDetail(id);
    }

    @GetMapping("/quote/{id}")
    public QuoteVO quote(@PathVariable("id") String id) {
        return service.quote(id);
    }

    /** 条文列表（17 号手册 A1）：支持语料 / 经典 / 关键词 + 分页。 */
    @GetMapping("/quote/list")
    public QuoteListVO quoteList(
            @RequestParam(value = "q", required = false, defaultValue = "") String q,
            @RequestParam(value = "bookId", required = false) String bookId,
            @RequestParam(value = "classicId", required = false) String classicId,
            @RequestParam(value = "page", required = false, defaultValue = "1") int page,
            @RequestParam(value = "size", required = false, defaultValue = "20") int size) {
        return service.quoteList(q, bookId, classicId, page, size);
    }

    /** 关联方剂 / 医案 / 条文（09 契约 §4 列出的 related 端点）。 */
    @GetMapping("/formula/{id}/related")
    public List<FormulaBriefVO> related(@PathVariable("id") String id) {
        return service.formula(id).related();
    }

    @GetMapping("/daily")
    public FormulaVO daily(@RequestParam(value = "bookId", required = false) String bookId) {
        return service.daily(bookId);
    }

    @GetMapping("/graph-preview")
    public GraphPreviewVO graphPreview(@RequestParam("formulaId") String formulaId) {
        return service.graphPreview(formulaId);
    }

    @PostMapping("/batch")
    public List<FormulaBriefVO> batch(@RequestBody Map<String, List<String>> body) {
        return service.batch(body.get("ids"), body.get("names"));
    }

    // ---------- 统计 ----------

    @GetMapping("/stats")
    public CatalogStatsVO stats() {
        return new CatalogStatsVO(
                bookMapper.allBookIds().size(),
                bookMapper.countAllNodes(),
                bookMapper.countAllFormulas(),
                bookMapper.countAllCases(),
                bookMapper.countAllQuotes(),
                bookMapper.countAllVectors());
    }
}
