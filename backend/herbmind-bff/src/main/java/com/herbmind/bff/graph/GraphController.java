package com.herbmind.bff.graph;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import com.herbmind.common.R;
import com.herbmind.contract.graph.FormulaGraphVO;
import com.herbmind.contract.graph.GraphClient;
import com.herbmind.contract.graph.GraphMapVO;
import com.herbmind.contract.graph.NeighborsVO;
import com.herbmind.contract.graph.PathVO;
import com.herbmind.contract.graph.SubgraphVO;

/**
 * 智能域 BFF（知识图谱：邻居 / 子图 / 方心子图 / 路径 / 相似度地图）。
 *
 * <p>对应 09 契约 §15.6 步骤 2 —— svc-graph 的五个 <b>/internal</b> 端点早已就绪，
 * 缺的就是这一层转发。本类只做**薄转发**：包 {@code R<T>} 外壳、原样透传参数与结果，
 * 不写业务规则、不做字段映射（svc-graph 的 DTO 与契约 §15 已逐字对齐）。
 *
 * <p>错误口径由 {@link GraphExceptionAdvice} 兜住：svc-graph 的 4040（实体不存在）
 * 若被 common 的全局兜底吃掉会变成 5000，前端就无法区分"传错了"和"库里没有"。
 */
@RestController
@RequestMapping("/api/biz/graph")
public class GraphController {

    private final GraphClient graph;

    public GraphController(GraphClient graph) {
        this.graph = graph;
    }

    /** 15.1 单实体邻居（图谱探索页）。 */
    @GetMapping("/neighbors")
    public R<NeighborsVO> neighbors(
            @RequestParam("entity") String entity,
            @RequestParam(value = "label", required = false) String label,
            @RequestParam(value = "hops", required = false, defaultValue = "1") int hops,
            @RequestParam(value = "limit", required = false, defaultValue = "50") int limit) {
        return R.ok(graph.neighbors(entity, label, hops, limit));
    }

    /** 15.2 子图（多起点 / 类型筛选）。entity 不传 = 全图（受 limit 限制）。 */
    @GetMapping("/subgraph")
    public R<SubgraphVO> subgraph(
            @RequestParam(value = "entity", required = false) String entity,
            @RequestParam(value = "label", required = false) String label,
            @RequestParam(value = "hops", required = false, defaultValue = "2") int hops,
            @RequestParam(value = "types", required = false) String types,
            @RequestParam(value = "limit", required = false, defaultValue = "200") int limit) {
        return R.ok(graph.subgraph(entity, label, hops, types, limit));
    }

    /**
     * 15.3 方心子图。
     *
     * <p>{@code id} 支持 {@code f_1} / 裸 {@code 1} / 方名；方名重名时后端返回 4000 并给出候选 ID
     * （库里确有两首「葛根汤」这类情况，不能替调用方猜）。
     */
    @GetMapping("/formula/{id}")
    public R<FormulaGraphVO> formula(@PathVariable("id") String id) {
        return R.ok(graph.formula(id));
    }

    /** 15.4 两实体之间的路径。{@code found=false} 不是错误，是「N 跳内无关联」。 */
    @GetMapping("/path")
    public R<PathVO> path(
            @RequestParam("from") String from,
            @RequestParam("to") String to,
            @RequestParam(value = "maxHops", required = false, defaultValue = "3") int maxHops,
            @RequestParam(value = "limit", required = false, defaultValue = "3") int limit) {
        return R.ok(graph.path(from, to, maxHops, limit));
    }

    /** 15.5 相似度地图坐标（服务端确定性计算，同 version 可复现）。 */
    @GetMapping("/map")
    public R<GraphMapVO> map(
            @RequestParam(value = "metric", required = false) String metric,
            @RequestParam(value = "limit", required = false, defaultValue = "200") int limit,
            @RequestParam(value = "nodeId", required = false) String nodeId) {
        return R.ok(graph.map(metric, limit, nodeId));
    }
}
