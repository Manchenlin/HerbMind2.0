package com.herbmind.contract.catalog;

import java.util.List;

import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestParam;

/**
 * svc-catalog 内部契约（OpenFeign 4.x：禁类级 @RequestMapping，用 path 属性）。
 *
 * 注意：/internal/** 内部接口返回**裸 DTO**（不包 R），由 BFF 统一包 R 给前端。
 * url 默认本地直连；上 Nacos 时用配置覆盖 herbmind.svc-catalog-url。
 */
@FeignClient(name = "svc-catalog", path = "/internal/catalog",
        url = "${herbmind.svc-catalog-url:http://localhost:8082}")
public interface CatalogClient {

    @GetMapping("/books")
    List<BookVO> books();

    @PostMapping("/import")
    ImportStatusVO importBook(@RequestBody ImportRequest request);

    @GetMapping("/import/{id}")
    ImportStatusVO importStatus(@PathVariable("id") String importId);

    @GetMapping("/tree")
    List<BookTreeNode> tree(@RequestParam("bookId") String bookId);

    @GetMapping("/node/{id}")
    BookTreeNode node(@PathVariable("id") String id);

    @GetMapping("/node/{id}/detail")
    NodeDetailVO nodeDetail(@PathVariable("id") String id);

    @GetMapping("/formula/{id}")
    FormulaVO formula(@PathVariable("id") String id);

    @GetMapping("/case/{id}")
    CaseVO caseRecord(@PathVariable("id") String id);

    @GetMapping("/quote/{id}")
    QuoteVO quote(@PathVariable("id") String id);

    /** 条文列表（A1）。 */
    @GetMapping("/quote/list")
    QuoteListVO quoteList(@RequestParam(value = "q", required = false) String q,
                          @RequestParam(value = "bookId", required = false) String bookId,
                          @RequestParam(value = "classicId", required = false) String classicId,
                          @RequestParam(value = "page", defaultValue = "1") int page,
                          @RequestParam(value = "size", defaultValue = "20") int size);

    @GetMapping("/formula/{id}/related")
    List<FormulaBriefVO> related(@PathVariable("id") String id);

    @GetMapping("/stats")
    CatalogStatsVO stats();

    /** 今日方证：按日期确定性挑选，首页用。 */
    @GetMapping("/daily")
    FormulaVO daily(@RequestParam(value = "bookId", required = false) String bookId);

    /** 首页图谱预览（内容域轻量版，不依赖 svc-graph）。 */
    @GetMapping("/graph-preview")
    GraphPreviewVO graphPreview(@RequestParam("formulaId") String formulaId);

    /** 按 id / 名称批量取方剂摘要（供域2 练习题面）。 */
    @PostMapping("/batch")
    List<FormulaBriefVO> batch(@RequestBody BatchQuery query);

    record BatchQuery(List<String> ids, List<String> names) {
    }
}
