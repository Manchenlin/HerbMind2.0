package com.herbmind.contract.graph;

import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestParam;

/**
 * svc-graph 内部契约（OpenFeign 4.x：禁类级 {@code @RequestMapping}，用 path 属性）。
 *
 * <p>对应 09 契约 §15 的五个 BFF 端点数据源。/internal/** 返回**裸 DTO**（不包 R），
 * 由 BFF 的 {@code GraphController} 统一包 {@code R<T>} 给前端 —— 与 svc-catalog 同一约定。
 *
 * <p>参数名必须与 {@code InternalGraphController} 的 {@code @RequestParam} 逐字一致，
 * 否则 Feign 拼出来的 query 后端收不到（表现为必填参数缺失 4000）。
 *
 * <p>错误口径：4000 参数错误 / 4040 实体不存在（由 BFF 侧 advice 映射回 4xx，别让它变成 5000）。
 */
@FeignClient(name = "svc-graph", path = "/internal/graph",
        url = "${herbmind.svc-graph-url:http://localhost:8085}")
public interface GraphClient {

    /** 15.1 单实体邻居。entity 接受实体名或业务 ID（麻黄汤 / f_1 / 麻黄 / h_麻黄）。 */
    @GetMapping("/neighbors")
    NeighborsVO neighbors(@RequestParam("entity") String entity,
                          @RequestParam(value = "label", required = false) String label,
                          @RequestParam(value = "hops", defaultValue = "1") int hops,
                          @RequestParam(value = "limit", defaultValue = "50") int limit);

    /** 15.2 子图。entity 逗号分隔最多 5 个；不传 = 全图（受 limit 限制）。 */
    @GetMapping("/subgraph")
    SubgraphVO subgraph(@RequestParam(value = "entity", required = false) String entity,
                        @RequestParam(value = "label", required = false) String label,
                        @RequestParam(value = "hops", defaultValue = "2") int hops,
                        @RequestParam(value = "types", required = false) String types,
                        @RequestParam(value = "limit", defaultValue = "200") int limit);

    /** 15.3 方心子图。id 支持 f_1 / 裸 1 / 方名；方名重名时后端返回 4000 并给出候选。 */
    @GetMapping("/formula/{id}")
    FormulaGraphVO formula(@PathVariable("id") String id);

    /** 15.4 两实体之间的路径。 */
    @GetMapping("/path")
    PathVO path(@RequestParam("from") String from,
                @RequestParam("to") String to,
                @RequestParam(value = "maxHops", defaultValue = "3") int maxHops,
                @RequestParam(value = "limit", defaultValue = "3") int limit);

    /** 15.5 相似度地图坐标。 */
    @GetMapping("/map")
    GraphMapVO map(@RequestParam(value = "metric", required = false) String metric,
                   @RequestParam(value = "limit", defaultValue = "200") int limit,
                   @RequestParam(value = "nodeId", required = false) String nodeId);
}
