package com.herbmind.svc.graph.controller;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import com.herbmind.svc.graph.dto.FormulaGraph;
import com.herbmind.svc.graph.dto.GraphMap;
import com.herbmind.svc.graph.dto.Neighbors;
import com.herbmind.svc.graph.dto.PathResult;
import com.herbmind.svc.graph.dto.Subgraph;
import com.herbmind.svc.graph.service.GraphQueryService;

/**
 * 内部接口（/internal/**，不进网关），对应 09 契约 §15 的五个 BFF 端点数据源。
 *
 * 返回**裸 DTO**（不包 R），由 BFF 统一包 R&lt;T&gt; 给前端 —— 与 svc-catalog 保持同一约定。
 * 错误口径：
 *   4000 参数错误（entity 为空 / label 不支持 / hops 越界）→ herbmind-common 的 GlobalExceptionHandler
 *   4040 实体不存在 → 本模块 GraphExceptionHandler（common 里没有 4040 分支）
 *   5000 Neo4j / PG 不可用 → common 兜底
 */
@RestController
@RequestMapping("/internal/graph")
public class InternalGraphController {

    private final GraphQueryService service;

    public InternalGraphController(GraphQueryService service) {
        this.service = service;
    }

    /**
     * 15.1 单实体邻居（图谱探索页）。
     *
     * @param entity 实体名或业务 ID（麻黄汤 / f_1 / 麻黄 / h_麻黄）
     * @param label  Formula（默认）或 Herb，也接受中文「方剂」「药味」
     * @param hops   1~3，默认 1；超过 3 报 4000
     * @param limit  邻居上限，默认 50，最大 200
     */
    @GetMapping("/neighbors")
    public Neighbors neighbors(
            @RequestParam("entity") String entity,
            @RequestParam(value = "label", required = false) String label,
            @RequestParam(value = "hops", defaultValue = "1") int hops,
            @RequestParam(value = "limit", defaultValue = "50") int limit) {
        return service.neighbors(entity, label, hops, limit);
    }

    /**
     * 15.2 子图（多起点 / 类型筛选，供相似度地图与批量渲染）。
     *
     * @param entity 起点实体，逗号分隔最多 5 个；**不传 = 全图**（受 limit 限制）
     * @param label  起点标签，默认 Formula
     * @param hops   1~3，默认 2
     * @param types  只要这些节点类型，逗号分隔（Formula,Herb），默认两者都要
     * @param limit  节点上限，默认 200，最大 500
     */
    @GetMapping("/subgraph")
    public Subgraph subgraph(
            @RequestParam(value = "entity", required = false) String entity,
            @RequestParam(value = "label", required = false) String label,
            @RequestParam(value = "hops", defaultValue = "2") int hops,
            @RequestParam(value = "types", required = false) String types,
            @RequestParam(value = "limit", defaultValue = "200") int limit) {
        return service.subgraph(entity, label, hops, types, limit);
    }

    /**
     * 15.3 方心子图（方剂详情页 / 图谱页中心块）。
     *
     * @param id 方剂 ID（f_1，也接受裸 1）；**兼容方名**（麻黄汤），
     *           但方名重名时返回 4000 并给出候选 ID（库里确有两首「葛根汤」这类情况，不能替你猜）
     */
    @GetMapping("/formula/{id}")
    public FormulaGraph formula(@PathVariable("id") String id) {
        return service.formulaGraph(id);
    }

    /**
     * 15.4 两实体之间的路径。
     *
     * @param from    起点（业务 ID 或名称）
     * @param to      终点
     * @param maxHops 1~4，默认 3
     * @param limit   最多几条路径，默认 3，最大 5
     */
    @GetMapping("/path")
    public PathResult path(
            @RequestParam("from") String from,
            @RequestParam("to") String to,
            @RequestParam(value = "maxHops", defaultValue = "3") int maxHops,
            @RequestParam(value = "limit", defaultValue = "3") int limit) {
        return service.path(from, to, maxHops, limit);
    }

    /**
     * 15.5 相似度地图坐标。
     *
     * @param metric 一期只允许 composition（药味 Jaccard），默认 composition
     * @param limit  点数，默认 200，最大 500
     * @param nodeId 可选：限定某目录节点（含子节点）下的方剂
     */
    @GetMapping("/map")
    public GraphMap map(
            @RequestParam(value = "metric", required = false) String metric,
            @RequestParam(value = "limit", defaultValue = "200") int limit,
            @RequestParam(value = "nodeId", required = false) String nodeId) {
        return service.map(metric, limit, nodeId);
    }
}
