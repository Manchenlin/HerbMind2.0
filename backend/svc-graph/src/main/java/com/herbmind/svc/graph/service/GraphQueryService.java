package com.herbmind.svc.graph.service;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import org.neo4j.driver.Driver;
import org.neo4j.driver.Record;
import org.neo4j.driver.Result;
import org.neo4j.driver.Session;
import org.neo4j.driver.types.Node;
import org.neo4j.driver.types.Path;
import org.neo4j.driver.types.Relationship;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import com.herbmind.svc.graph.dto.GraphEdge;
import com.herbmind.svc.graph.dto.GraphNode;
import com.herbmind.svc.graph.dto.Subgraph;

/**
 * 图谱查询：目前只做「邻居子图」。
 *
 * 真实图模型（见 database/etl/build_graph.py）：
 *   (:Formula {id, name, syndrome, page}) -[:COMPOSED_OF {dose, unit, role}]-> (:Herb {name})
 * 注意只有 2 类节点、1 类关系 —— 原型里的 Syndrome / Symptom 节点**尚未入库**。
 */
@Service
public class GraphQueryService {

    private static final Logger log = LoggerFactory.getLogger(GraphQueryService.class);

    /** 跳数上限 3：245 首方经由药味高度互联，2 跳就能拉到半个图，再不设限会拖垮服务 */
    private static final int MAX_HOPS = 3;
    private static final int MAX_LIMIT = 1000;

    private final Driver driver;

    public GraphQueryService(Driver driver) {
        this.driver = driver;
    }

    /**
     * 取某实体的 1..N 跳邻居子图。
     *
     * @param entity 方名或方剂 ID（如 麻黄汤 / f_3），也支持药名
     * @param hops   跳数，超出 1..3 会被夹紧
     * @param limit  最多返回多少条路径（防扇出）
     */
    public Subgraph neighbors(String entity, int hops, int limit) {
        String key = entity == null ? "" : entity.trim();
        if (key.isEmpty()) {
            throw new IllegalArgumentException("entity 不能为空：请传方名或方剂 ID，如 麻黄汤");
        }
        int h = Math.min(Math.max(hops, 1), MAX_HOPS);
        int lim = Math.min(Math.max(limit, 1), MAX_LIMIT);

        try (Session session = driver.session()) {
            GraphNode center = findCenter(session, key);
            if (center == null) {
                throw new IllegalArgumentException("图中找不到实体：" + key);
            }

            // 路径长度无法参数化，只能拼进语句；h 已被夹到 1..3（int），不存在注入面
            String cypher = "MATCH p = (c)-[*1.." + h + "]-(other) "
                    + "WHERE elementId(c) = $cid "
                    + "RETURN p LIMIT $limit";

            Map<String, GraphNode> nodes = new LinkedHashMap<>();
            Map<String, GraphEdge> edges = new LinkedHashMap<>();
            nodes.put(center.id(), center);

            int rows = 0;
            Result result = session.run(cypher, Map.of("cid", center.id(), "limit", lim));
            while (result.hasNext()) {
                Record rec = result.next();
                rows++;
                Path path = rec.get("p").asPath();
                for (Node n : path.nodes()) {
                    nodes.putIfAbsent(n.elementId(), toNode(n));
                }
                for (Relationship r : path.relationships()) {
                    edges.putIfAbsent(r.elementId(), toEdge(r));
                }
            }

            boolean truncated = rows >= lim;
            log.info("neighbors：entity={} hops={} limit={} → nodes={} edges={} truncated={}",
                    key, h, lim, nodes.size(), edges.size(), truncated);

            return new Subgraph(center, List.copyOf(nodes.values()), List.copyOf(edges.values()), h, truncated);
        }
    }

    /** 按 name 或 id 定位中心节点；两边都试，因为 Formula 两个属性都可能被当作入参（前端更常给名字） */
    private GraphNode findCenter(Session session, String key) {
        Result r = session.run("""
                MATCH (c)
                WHERE c.name = $key OR c.id = $key
                RETURN c
                LIMIT 1
                """, Map.of("key", key));
        return r.hasNext() ? toNode(r.next().get("c").asNode()) : null;
    }

    private GraphNode toNode(Node n) {
        Map<String, Object> props = new LinkedHashMap<>(n.asMap());
        String label = n.labels().iterator().hasNext() ? n.labels().iterator().next() : "Unknown";
        String name = props.get("name") != null ? String.valueOf(props.get("name"))
                : props.get("id") != null ? String.valueOf(props.get("id"))
                : label + ":" + n.elementId();
        return new GraphNode(n.elementId(), label, name, props.isEmpty() ? null : props);
    }

    private GraphEdge toEdge(Relationship r) {
        Map<String, Object> props = new LinkedHashMap<>(r.asMap());
        return new GraphEdge(r.startNodeElementId(), r.endNodeElementId(), r.type(),
                props.isEmpty() ? null : props);
    }
}
