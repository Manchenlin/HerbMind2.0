package com.herbmind.contract.catalog;

import java.util.List;

import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
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

    @GetMapping("/tree")
    List<BookTreeNode> tree(@RequestParam("bookId") String bookId);

    @GetMapping("/node/{id}")
    BookTreeNode node(@PathVariable("id") String id);
}
