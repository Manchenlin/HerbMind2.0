package com.herbmind.bff.catalog;

import java.util.List;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import com.herbmind.common.R;
import com.herbmind.contract.catalog.BookTreeNode;
import com.herbmind.contract.catalog.BookVO;
import com.herbmind.contract.catalog.CaseVO;
import com.herbmind.contract.catalog.CatalogClient;
import com.herbmind.contract.catalog.FormulaVO;
import com.herbmind.contract.catalog.ImportRequest;
import com.herbmind.contract.catalog.ImportStatusVO;
import com.herbmind.contract.catalog.NodeDetailVO;
import com.herbmind.contract.catalog.QuoteListVO;
import com.herbmind.contract.catalog.QuoteVO;

/**
 * 内容域 BFF（书架 / 目录 / 方剂 / 医案 / 条文 / 导入）。
 * 前端只认 /api/biz/**；这里包装 R&lt;T&gt; 并做轻量编排，不写业务规则。
 */
@RestController
@RequestMapping("/api/biz")
public class CatalogController {

    private final CatalogClient catalog;

    public CatalogController(CatalogClient catalog) {
        this.catalog = catalog;
    }

    // ---------- 书架 / 导入 ----------

    @GetMapping("/catalog/books")
    public R<List<BookVO>> books() {
        return R.ok(catalog.books());
    }

    @PostMapping("/catalog/import")
    public R<ImportStatusVO> importBook(@RequestBody ImportRequest request) {
        return R.ok(catalog.importBook(request));
    }

    @GetMapping("/catalog/import/{id}")
    public R<ImportStatusVO> importStatus(@PathVariable("id") String id) {
        return R.ok(catalog.importStatus(id));
    }

    // ---------- 目录 ----------

    @GetMapping("/library/tree")
    public R<List<BookTreeNode>> tree(
            @RequestParam(value = "bookId", required = false, defaultValue = "bk_1") String bookId) {
        return R.ok(catalog.tree(bookId));
    }

    @GetMapping("/catalog/node/{id}")
    public R<NodeDetailVO> node(@PathVariable("id") String id) {
        return R.ok(catalog.nodeDetail(id));
    }

    // ---------- 方剂 / 医案 / 条文 ----------

    @GetMapping("/formula/{id}/page")
    public R<FormulaVO> formula(@PathVariable("id") String id) {
        return R.ok(catalog.formula(id));
    }

    @GetMapping("/case/{id}/page")
    public R<CaseVO> casePage(@PathVariable("id") String id) {
        return R.ok(catalog.caseRecord(id));
    }

    @GetMapping("/quote/{id}/page")
    public R<QuoteVO> quote(@PathVariable("id") String id) {
        return R.ok(catalog.quote(id));
    }

    /** 条文列表（17 号手册 A1）：前端条文索引 / 选条场景可直接用。 */
    @GetMapping("/quote/list")
    public R<QuoteListVO> quoteList(
            @RequestParam(value = "q", required = false, defaultValue = "") String q,
            @RequestParam(value = "bookId", required = false) String bookId,
            @RequestParam(value = "classicId", required = false) String classicId,
            @RequestParam(value = "page", required = false, defaultValue = "1") int page,
            @RequestParam(value = "size", required = false, defaultValue = "20") int size) {
        return R.ok(catalog.quoteList(q == null ? "" : q, bookId == null ? "" : bookId,
                classicId == null ? "" : classicId, page, size));
    }
}
