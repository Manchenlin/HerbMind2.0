package com.herbmind.svc.graph.controller;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import com.herbmind.svc.graph.dto.Subgraph;
import com.herbmind.svc.graph.service.GraphQueryService;

/**
 * 内部接口（/internal/**，不进网关）。
 *
 * 返回**裸 DTO**（不包 R），由 BFF 统一包 R&lt;T&gt; 给前端 —— 与 svc-catalog 保持同一约定。
 * 参数非法（空 entity / 实体不存在）抛 IllegalArgumentException，由 herbmind-common 的
 * GlobalExceptionHandler 转成 {code:4000,msg:"..."}。
 */
@RestController
@RequestMapping("/internal/graph")
public class InternalGraphController {

    private final GraphQueryService service;

    public InternalGraphController(GraphQueryService service) {
        this.service = service;
    }

    /**
     * 邻居子图。
     *
     * @param entity 方名或方剂 ID（如 麻黄汤 / f_3）
     * @param hops   跳数，默认 1，范围 1..3（超出会被夹紧而不是报错）
     * @param limit  最多返回路径条数，默认 200，上限 1000
     */
    @GetMapping("/neighbors")
    public Subgraph neighbors(
            @RequestParam("entity") String entity,
            @RequestParam(value = "hops", defaultValue = "1") int hops,
            @RequestParam(value = "limit", defaultValue = "200") int limit) {
        return service.neighbors(entity, hops, limit);
    }
}
