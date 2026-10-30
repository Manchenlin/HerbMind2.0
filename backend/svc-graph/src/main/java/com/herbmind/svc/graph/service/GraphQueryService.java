package com.herbmind.svc.graph.service;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

import org.neo4j.driver.Driver;
import org.neo4j.driver.Record;
import org.neo4j.driver.Result;
import org.neo4j.driver.Session;
import org.neo4j.driver.Value;
import org.neo4j.driver.types.Node;
import org.neo4j.driver.types.Path;
import org.neo4j.driver.types.Relationship;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

import com.herbmind.svc.graph.dto.FormulaGraph;
import com.herbmind.svc.graph.dto.GraphEdge;
import com.herbmind.svc.graph.dto.GraphMap;
import com.herbmind.svc.graph.dto.GraphNode;
import com.herbmind.svc.graph.dto.Neighbors;
import com.herbmind.svc.graph.dto.PathResult;
import com.herbmind.svc.graph.dto.Subgraph;
import com.herbmind.svc.graph.exception.GraphEntityNotFoundException;
import com.herbmind.svc.graph.repo.CompositionRepository;
import com.herbmind.svc.graph.repo.CompositionRepository.FormulaRow;
import com.herbmind.svc.graph.repo.CompositionRepository.HerbRow;
import com.herbmind.svc.graph.support.GraphIds;

/**
 * 图谱查询（09 契约 §15，`/internal/graph/**` 五个端点）。
 *
 * 真实图模型（见 database/etl/build_graph.py）：
 *   (:Formula {id, name, syndrome, page}) -[:COMPOSED_OF {dose, unit, role}]-> (:Herb {name})
 * 注意只有 2 类节点、1 类关系 —— 原型里的 Syndrome / Symptom 节点**尚未入库**，
 * 所以所有接口只接受 Formula / Herb，收到别的标签一律 4000，不做"猜你想查什么"。
 *
 * 数据来源分工：
 *   · 图结构（邻居、多跳、路径）→ Neo4j；
 *   · 药味顺序 seq、剂量、脏药名、Jaccard → PG（Neo4j 里没有 seq，关联方只能在 PG 侧算）；
 *   · 相似度地图坐标 → 服务端确定性计算（{@link CompositionAnalytics}）。
 *
 * 对外 ID 一律 f_* / h_*（{@link GraphIds}），不暴露 elementId。
 */
@Service
public class GraphQueryService {

    private static final Logger log = LoggerFactory.getLogger(GraphQueryService.class);

    /** 跳数上限 3：245 首方经由药味高度互联，再往上拉会拖垮服务（契约 §15.2 性能约束同源） */
    private static final int MAX_HOPS = 3;
    private static final int DEFAULT_NEIGHBOR_HOPS = 1;
    private static final int DEFAULT_SUBGRAPH_HOPS = 2;
    private static final int MAX_NEIGHBOR_LIMIT = 200;
    private static final int DEFAULT_NEIGHBOR_LIMIT = 50;
    private static final int MAX_SUBGRAPH_LIMIT = 500;
    private static final int DEFAULT_SUBGRAPH_LIMIT = 200;
    private static final int MAX_SUBGRAPH_STARTS = 5;
    private static final int MAX_PATH_HOPS = 4;
    private static final int DEFAULT_PATH_HOPS = 3;
    private static final int MAX_PATH_LIMIT = 5;
    private static final int DEFAULT_PATH_LIMIT = 3;
    private static final int MAX_MAP_POINTS = 500;
    private static final int DEFAULT_MAP_POINTS = 200;

    /** 输出顺序：先按 label（Formula 在前），再按 name —— 契约 §15.1 要求稳定顺序 */
    private static final Comparator<GraphNode> NODE_ORDER =
            Comparator.comparing(GraphNode::label).thenComparing(GraphNode::name);

    private final Driver driver;
    private final CompositionRepository repository;

    public GraphQueryService(Driver driver, CompositionRepository repository) {
        this.driver = driver;
        this.repository = repository;
    }

    // ================================================================== 15.1 邻居

    /**
     * 取某实体的 1..N 跳邻居（不含 center 自身）。
     *
     * @param entity 实体名或业务 ID（如 麻黄汤 / f_1 / 麻黄 / h_麻黄）
     * @param label  Formula / 方剂（默认）或 Herb / 药味
     * @param hops   1..3，超出报 4000（契约 §15.1 错误码）
     * @param limit  邻居上限，默认 50，最大 200（超出按 200 夹紧）
     */
    public Neighbors neighbors(String entity, String label, int hops, int limit) {
        String type = normalizeLabel(label);
        int h = hops <= 0 ? DEFAULT_NEIGHBOR_HOPS : hops;
        if (h > MAX_HOPS) {
            throw new IllegalArgumentException("hops 只支持 1~" + MAX_HOPS + "，收到：" + hops);
        }
        int lim = limit <= 0 ? DEFAULT_NEIGHBOR_LIMIT : Math.min(limit, MAX_NEIGHBOR_LIMIT);

        try (Session session = driver.session()) {
            Node centerNode = findNode(session, type, entity);
            if (centerNode == null) {
                throw new GraphEntityNotFoundException("图中找不到实体：" + entity + "（label=" + type + "）");
            }
            GraphNode center = toNode(centerNode);

            Map<String, Node> found = new LinkedHashMap<>();
            // 路径长度无法参数化，只能拼进语句；h 已被夹到 1..3（int），不存在注入面
            String cypher = "MATCH p=(c)-[*1.." + h + "]-(n) "
                    + "WHERE elementId(c) = $cid AND (n:Formula OR n:Herb) RETURN n";
            Result result = session.run(cypher, Map.of("cid", centerNode.elementId()));
            while (result.hasNext()) {
                Node n = result.next().get("n").asNode();
                found.putIfAbsent(n.elementId(), n);
            }

            List<NodePair> all = new ArrayList<>();
            for (Node n : found.values()) {
                GraphNode vo = toNode(n);
                // 多跳路径可能绕回 center 自己
                if (!vo.id().equals(center.id())) {
                    all.add(new NodePair(n, vo));
                }
            }
            all.sort((x, y) -> NODE_ORDER.compare(x.vo(), y.vo()));

            boolean truncated = all.size() > lim;
            List<NodePair> kept = truncated ? all.subList(0, lim) : all;

            Set<String> elementIds = new LinkedHashSet<>();
            elementIds.add(centerNode.elementId());
            List<GraphNode> nodes = new ArrayList<>(kept.size());
            for (NodePair p : kept) {
                elementIds.add(p.node().elementId());
                nodes.add(p.vo());
            }

            // 只保留一端是 center 的边（契约 §15.1：edges = 邻居与 center 之间的边）
            List<GraphEdge> edges = new ArrayList<>();
            for (GraphEdge e : edgesAmong(session, elementIds)) {
                if (e.source().equals(center.id()) || e.target().equals(center.id())) {
                    edges.add(e);
                }
            }

            log.info("neighbors：entity={} label={} hops={} limit={} → nodes={} edges={} truncated={}",
                    entity, type, h, lim, nodes.size(), edges.size(), truncated);
            return new Neighbors(center, nodes, edges, truncated);
        }
    }

    // ================================================================== 15.2 子图

    /**
     * 多起点子图（供相似度地图与批量渲染）。
     *
     * @param entitiesCsv 起点实体，逗号分隔最多 5 个；不传 = 全图（受 limit 限制）
     * @param label       起点标签，默认 Formula
     * @param hops        1..3，默认 2（超出夹紧而不是报错）
     * @param typesCsv    只要这些节点类型，逗号分隔，默认两者都要
     * @param limit       节点上限，默认 200，最大 500
     */
    public Subgraph subgraph(String entitiesCsv, String label, int hops, String typesCsv, int limit) {
        String type = normalizeLabel(label);
        int h = clamp(hops <= 0 ? DEFAULT_SUBGRAPH_HOPS : hops, 1, MAX_HOPS);
        Set<String> types = parseTypes(typesCsv);
        int lim = clamp(limit <= 0 ? DEFAULT_SUBGRAPH_LIMIT : limit, 1, MAX_SUBGRAPH_LIMIT);

        try (Session session = driver.session()) {
            Map<String, DistNode> byElementId = new LinkedHashMap<>();

            if (entitiesCsv == null || entitiesCsv.isBlank()) {
                Result result = session.run("MATCH (n) WHERE n:Formula OR n:Herb RETURN n");
                while (result.hasNext()) {
                    collect(result.next().get("n").asNode(), 0, types, byElementId);
                }
            } else {
                List<String> keys = splitCsv(entitiesCsv);
                if (keys.size() > MAX_SUBGRAPH_STARTS) {
                    throw new IllegalArgumentException("entity 最多 " + MAX_SUBGRAPH_STARTS + " 个起点，收到 "
                            + keys.size() + " 个");
                }
                List<String> resolved = new ArrayList<>();
                List<String> missing = new ArrayList<>();
                for (String key : keys) {
                    Node n = findNode(session, type, key);
                    if (n == null) {
                        missing.add(key);
                    } else {
                        resolved.add(n.elementId());
                        collect(n, 0, types, byElementId);
                    }
                }
                if (resolved.isEmpty()) {
                    throw new GraphEntityNotFoundException(
                            "起点实体全部不存在：" + String.join("、", missing) + "（label=" + type + "）");
                }
                if (!missing.isEmpty()) {
                    log.info("subgraph：忽略不存在的起点 {}", missing);
                }

                // 带 min(length(p)) 是为了按"离起点几跳"排序后再截断：
                // 若只按 label 排序，limit 小时会整类截掉（曾出现 8 个节点全是方剂、一条边都没有）
                String cypher = "MATCH p=(c)-[*1.." + h + "]-(n) "
                        + "WHERE elementId(c) IN $cids AND (n:Formula OR n:Herb) "
                        + "RETURN n, min(length(p)) AS d";
                Result result = session.run(cypher, Map.of("cids", resolved));
                while (result.hasNext()) {
                    Record rec = result.next();
                    collect(rec.get("n").asNode(), rec.get("d").asInt(), types, byElementId);
                }
            }

            List<DistNode> all = new ArrayList<>(byElementId.values());
            // 先近后远，同距离按名称混排（不先按 label，避免整类被 limit 挤掉）
            all.sort(Comparator.comparingInt(DistNode::distance)
                    .thenComparing(d -> d.vo().name())
                    .thenComparing(d -> d.vo().label()));

            boolean truncated = all.size() > lim;
            List<DistNode> kept = truncated ? all.subList(0, lim) : all;

            Set<String> elementIds = new LinkedHashSet<>();
            List<GraphNode> nodes = new ArrayList<>(kept.size());
            for (DistNode p : kept) {
                elementIds.add(p.node().elementId());
                nodes.add(p.vo());
            }
            List<GraphEdge> edges = edgesAmong(session, elementIds);

            log.info("subgraph：entities={} label={} hops={} types={} limit={} → nodes={} edges={} truncated={}",
                    entitiesCsv, type, h, types, lim, nodes.size(), edges.size(), truncated);
            return new Subgraph(nodes, edges, new Subgraph.Stats(nodes.size(), edges.size()), truncated);
        }
    }

    // ================================================================== 15.3 方心子图

    /**
     * 方心子图：中心方剂 + 药味（含 seq）+ 药味最相近的成方（Jaccard）。
     *
     * 全部数据取自 PG —— Neo4j 里没有 seq，也没存别名/证候原文；
     * relatedFormulas 用药味集合 Jaccard（确定性规则），每条都要能被前端标注「组成相近 ≠ 同一方」。
     *
     * @param idOrName 方剂 ID（f_1，也接受裸 1）或方名（麻黄汤）；**方名重名时报 4000 并要求用 ID**
     */
    public FormulaGraph formulaGraph(String idOrName) {
        String raw = requireText(idOrName, "id");
        String fid = GraphIds.formulaId(raw);

        List<FormulaRow> formulas = repository.formulas();
        FormulaRow center = null;
        Map<String, String> names = new LinkedHashMap<>(formulas.size());
        for (FormulaRow row : formulas) {
            String rid = GraphIds.formulaId(row.id());
            names.put(rid, row.name() == null ? rid : row.name());
            if (rid.equals(fid)) {
                center = row;
            }
        }
        if (center == null) {
            // ID 没命中时再按方名找一次（前端详情页、手工核对常直接给名字）
            center = resolveFormulaByName(raw, formulas);
        }

        List<HerbRow> allRows = repository.herbRows();
        Map<String, List<HerbRow>> grouped = CompositionAnalytics.rowsByFormula(allRows);
        List<HerbRow> rows = grouped.getOrDefault(center.id(), List.of());

        List<HerbRow> ordered = new ArrayList<>(rows);
        ordered.sort(Comparator.comparingInt(HerbRow::seq).thenComparing(HerbRow::herbName,
                Comparator.nullsLast(Comparator.naturalOrder())));

        List<FormulaGraph.Herb> herbs = new ArrayList<>(ordered.size());
        for (HerbRow r : ordered) {
            herbs.add(new FormulaGraph.Herb(GraphIds.herbId(r.herbName()), r.herbName(),
                    r.seq(), r.dose(), r.unit(), r.role()));
        }

        Map<String, Set<String>> sets = CompositionAnalytics.herbSets(allRows);
        List<FormulaGraph.RelatedFormula> related = CompositionAnalytics.relatedFormulas(
                GraphIds.formulaId(center.id()), sets, names);

        boolean incomplete = CompositionAnalytics.isHerbsIncomplete(rows);
        log.info("formula：{} → id={} herbs={} incomplete={} related={}",
                raw, GraphIds.formulaId(center.id()), herbs.size(), incomplete, related.size());

        return new FormulaGraph(
                new FormulaGraph.Center(GraphIds.formulaId(center.id()), center.name(),
                        center.alias(), center.syndromeText(), center.page()),
                herbs, incomplete, related, CompositionAnalytics.NOTICE);
    }

    /**
     * 按方名解析方剂。
     *
     * **重名不猜**：库里确实存在同名不同方的记录（如两首「葛根汤」f_2 / f_128），
     * 随便取一首等于把错的数据当对的返回，所以这里报 4000 并把候选 ID 一并告诉调用方。
     */
    private FormulaRow resolveFormulaByName(String raw, List<FormulaRow> formulas) {
        String key = raw.trim();
        List<FormulaRow> hits = new ArrayList<>();
        for (FormulaRow row : formulas) {
            if (row.name() != null && row.name().trim().equals(key)) {
                hits.add(row);
            }
        }
        if (hits.isEmpty()) {
            throw new GraphEntityNotFoundException("方剂不存在：" + raw + "（ID 和方名都没匹配上）");
        }
        if (hits.size() > 1) {
            List<String> ids = new ArrayList<>(hits.size());
            for (FormulaRow row : hits) {
                ids.add(GraphIds.formulaId(row.id()));
            }
            ids.sort(GraphIds::compareById);
            throw new IllegalArgumentException("方名「" + key + "」在库内对应 " + hits.size()
                    + " 首方剂，请改用 ID 查询：" + String.join("、", ids));
        }
        return hits.get(0);
    }

    // ================================================================== 15.4 路径

    /**
     * 两实体之间的路径。
     *
     * @param from    起点（业务 ID 或名称）
     * @param to      终点
     * @param maxHops 1..4，默认 3（超出夹紧）
     * @param limit   最多返回几条，默认 3，最大 5
     */
    public PathResult path(String from, String to, int maxHops, int limit) {
        String fromKey = requireText(from, "from");
        String toKey = requireText(to, "to");
        int h = clamp(maxHops <= 0 ? DEFAULT_PATH_HOPS : maxHops, 1, MAX_PATH_HOPS);
        int lim = clamp(limit <= 0 ? DEFAULT_PATH_LIMIT : limit, 1, MAX_PATH_LIMIT);

        try (Session session = driver.session()) {
            Node a = resolveAny(session, fromKey);
            if (a == null) {
                throw new GraphEntityNotFoundException("起点实体不存在：" + fromKey);
            }
            Node b = resolveAny(session, toKey);
            if (b == null) {
                throw new GraphEntityNotFoundException("终点实体不存在：" + toKey);
            }
            if (a.elementId().equals(b.elementId())) {
                throw new IllegalArgumentException("起点与终点相同：" + fromKey);
            }

            GraphNode fromNode = toNode(a);
            GraphNode toNode = toNode(b);

            // 契约 §15.4 实现约束：必须带 LIMIT 与跳数上限，禁止无界 [*]
            String cypher = "MATCH p=(a)-[*1.." + h + "]-(b) "
                    + "WHERE elementId(a) = $aid AND elementId(b) = $bid "
                    + "RETURN p ORDER BY length(p) LIMIT $limit";
            Result result = session.run(cypher, Map.of("aid", a.elementId(), "bid", b.elementId(), "limit", lim));

            List<PathResult.GraphPath> paths = new ArrayList<>();
            while (result.hasNext()) {
                paths.add(toGraphPath(result.next().get("p").asPath()));
            }

            if (paths.isEmpty()) {
                String msg = "「" + fromNode.name() + "」与「" + toNode.name() + "」在 " + h + " 跳内无关联";
                log.info("path：{} → {} maxHops={} 无路径", fromKey, toKey, h);
                return new PathResult(false, List.of(), msg);
            }

            String explanation = explain(fromNode, toNode, paths.get(0));
            log.info("path：{} → {} maxHops={} → paths={}", fromKey, toKey, h, paths.size());
            return new PathResult(true, paths, explanation);
        }
    }

    /** 人类可读说明。只陈述图结构（谁和谁相连），不解读任何医理。 */
    private String explain(GraphNode from, GraphNode to, PathResult.GraphPath path) {
        int len = path.length();
        if (len == 1) {
            return "「" + from.name() + "」与「" + to.name() + "」直接相连（1 跳）";
        }
        if (len == 2) {
            GraphNode middle = path.nodes().get(1);
            if ("Herb".equals(middle.label())) {
                return "「" + from.name() + "」与「" + to.name() + "」经共享药味「" + middle.name() + "」相连（2 跳）";
            }
            return "「" + from.name() + "」与「" + to.name() + "」经「" + middle.name() + "」相连（2 跳）";
        }
        StringBuilder chain = new StringBuilder();
        for (GraphNode n : path.nodes()) {
            if (chain.length() > 0) {
                chain.append(" → ");
            }
            chain.append(n.name());
        }
        return "「" + from.name() + "」与「" + to.name() + "」经 " + len + " 跳相连：" + chain;
    }

    // ================================================================== 15.5 相似度地图

    /**
     * 相似度地图坐标：只允许药味 Jaccard 口径，坐标由服务端确定性计算。
     *
     * @param metric 一期只允许 composition
     * @param limit  点数，默认 200，最大 500（超出按 id 升序取前 N 个并标 truncated）
     * @param nodeId 可选：限定某目录节点（含其子节点）下的方剂
     */
    public GraphMap map(String metric, int limit, String nodeId) {
        String m = (metric == null || metric.isBlank())
                ? CompositionAnalytics.METRIC_COMPOSITION
                : metric.trim().toLowerCase(Locale.ROOT);
        if (!CompositionAnalytics.METRIC_COMPOSITION.equals(m)) {
            throw new IllegalArgumentException(
                    "metric 一期只支持 composition（药味 Jaccard），收到：" + metric);
        }
        int lim = clamp(limit <= 0 ? DEFAULT_MAP_POINTS : limit, 1, MAX_MAP_POINTS);

        Set<String> nodeFilter = null;
        if (nodeId != null && !nodeId.isBlank()) {
            nodeFilter = new LinkedHashSet<>(repository.descendantNodeIds(nodeId.trim()));
        }

        List<FormulaRow> formulas = repository.formulas();
        Map<String, Set<String>> sets = CompositionAnalytics.herbSets(repository.herbRows());
        Map<String, String> names = new LinkedHashMap<>();
        List<String> ids = new ArrayList<>();
        for (FormulaRow row : formulas) {
            if (nodeFilter != null && (row.nodeId() == null || !nodeFilter.contains(row.nodeId()))) {
                continue;
            }
            String id = GraphIds.formulaId(row.id());
            ids.add(id);
            names.put(id, row.name() == null ? id : row.name());
        }
        ids.sort(GraphIds::compareById);

        boolean truncated = ids.size() > lim;
        List<String> kept = truncated ? List.copyOf(ids.subList(0, lim)) : List.copyOf(ids);

        List<GraphMap.Point> points = CompositionAnalytics.points(kept, names, sets);
        String version = CompositionAnalytics.version(kept, sets);
        log.info("map：metric={} nodeId={} limit={} → points={} truncated={} version={}",
                m, nodeId, lim, points.size(), truncated, version);

        return new GraphMap(m, points, version, truncated);
    }

    // ================================================================== 内部工具

    private record NodePair(Node node, GraphNode vo) {
    }

    /** 子图收集用：带上"离起点几跳"，截断时先保近的。 */
    private record DistNode(Node node, GraphNode vo, int distance) {
    }

    /** 按业务 ID 口径把 Neo4j 节点转成对外 VO。 */
    private static GraphNode toNode(Node n) {
        String label = n.hasLabel("Formula") ? "Formula" : n.hasLabel("Herb") ? "Herb" : firstLabel(n);
        Map<String, Object> props = new LinkedHashMap<>();
        if ("Formula".equals(label)) {
            String rawId = text(n, "id");
            String bizId = GraphIds.formulaId(rawId != null ? rawId : text(n, "name"));
            putIfNotNull(props, "syndrome", text(n, "syndrome"));
            putIfNotNull(props, "page", text(n, "page"));
            String name = text(n, "name");
            return new GraphNode(bizId, label, name != null ? name : bizId, props);
        }
        String name = text(n, "name");
        String bizId = GraphIds.herbId(name);
        return new GraphNode(bizId, label, name != null ? name : bizId, props);
    }

    /**
     * 按 label 定位节点：先试 id / 带前缀与去前缀两种写法，再试 name。
     * 为什么两边都试：前端更常给名字（麻黄汤），而 URL / 收藏给的是 ID（f_1）。
     */
    private Node findNode(Session session, String label, String raw) {
        String key = requireText(raw, "entity");
        List<String> keys = "Formula".equals(label) ? formulaKeys(key) : herbKeys(key);
        String cypher = "Formula".equals(label)
                ? "MATCH (n:Formula) WHERE n.name IN $keys OR n.id IN $keys RETURN n LIMIT 1"
                : "MATCH (n:Herb) WHERE n.name IN $keys RETURN n LIMIT 1";
        Result result = session.run(cypher, Map.of("keys", keys));
        return result.hasNext() ? result.next().get("n").asNode() : null;
    }

    /** 路径接口不限定标签，两个标签都试（同名的方与药极少，先方后药）。 */
    private Node resolveAny(Session session, String raw) {
        Node n = findNode(session, "Formula", raw);
        return n != null ? n : findNode(session, "Herb", raw);
    }

    private List<String> formulaKeys(String key) {
        Set<String> keys = new LinkedHashSet<>();
        keys.add(key);
        String stripped = GraphIds.stripFormula(key);
        if (!stripped.isEmpty()) {
            keys.add(stripped);
            keys.add(GraphIds.formulaId(stripped));
        }
        return List.copyOf(keys);
    }

    private List<String> herbKeys(String key) {
        Set<String> keys = new LinkedHashSet<>();
        keys.add(key);
        String stripped = GraphIds.stripHerb(key);
        if (!stripped.isEmpty()) {
            keys.add(stripped);
        }
        return List.copyOf(keys);
    }

    /** 给定节点集合，取它们之间（双向）所有关系。 */
    private List<GraphEdge> edgesAmong(Session session, Set<String> elementIds) {
        if (elementIds.size() < 2) {
            return List.of();
        }
        Result result = session.run(
                "MATCH (a)-[rel]->(b) WHERE elementId(a) IN $ids AND elementId(b) IN $ids RETURN a, b, rel",
                Map.of("ids", List.copyOf(elementIds)));
        Map<String, GraphEdge> edges = new LinkedHashMap<>();
        while (result.hasNext()) {
            Record rec = result.next();
            GraphNode from = toNode(rec.get("a").asNode());
            GraphNode to = toNode(rec.get("b").asNode());
            Relationship rel = rec.get("rel").asRelationship();
            GraphEdge edge = new GraphEdge(from.id(), to.id(), rel.type(), propsOf(rel));
            edges.putIfAbsent(edge.source() + "|" + edge.target() + "|" + edge.rel(), edge);
        }
        return List.copyOf(edges.values());
    }

    private PathResult.GraphPath toGraphPath(Path p) {
        Map<String, String> bizIdByElement = new LinkedHashMap<>();
        List<GraphNode> nodes = new ArrayList<>();
        for (Node n : p.nodes()) {
            GraphNode vo = toNode(n);
            bizIdByElement.put(n.elementId(), vo.id());
            nodes.add(vo);
        }
        List<GraphEdge> edges = new ArrayList<>();
        for (Relationship rel : p.relationships()) {
            String source = bizIdByElement.get(rel.startNodeElementId());
            String target = bizIdByElement.get(rel.endNodeElementId());
            if (source == null || target == null) {
                continue;
            }
            edges.add(new GraphEdge(source, target, rel.type(), propsOf(rel)));
        }
        return new PathResult.GraphPath(nodes, edges, edges.size());
    }

    private Map<String, Object> propsOf(Relationship rel) {
        Map<String, Object> props = new LinkedHashMap<>();
        putIfNotNull(props, "dose", formatNumber(rel.get("dose").asObject()));
        putIfNotNull(props, "unit", text(rel, "unit"));
        putIfNotNull(props, "role", text(rel, "role"));
        return props;
    }

    private static String text(Relationship rel, String key) {
        Value v = rel.get(key);
        if (v == null || v.isNull()) {
            return null;
        }
        Object o = v.asObject();
        return o instanceof String s ? s : String.valueOf(o);
    }

    private static String text(Node n, String key) {
        Value v = n.get(key);
        if (v == null || v.isNull()) {
            return null;
        }
        Object o = v.asObject();
        return o instanceof String s ? s : String.valueOf(o);
    }

    private static String firstLabel(Node n) {
        return n.labels().iterator().hasNext() ? n.labels().iterator().next() : "Unknown";
    }

    private static void putIfNotNull(Map<String, Object> target, String key, Object value) {
        if (value != null) {
            target.put(key, value);
        }
    }

    /** 剂量在 Neo4j 里是 float：整数值去掉 .0，避免前端显示 9.0g。 */
    private static String formatNumber(Object value) {
        if (value == null) {
            return null;
        }
        if (value instanceof Double d) {
            return d == Math.rint(d) ? String.valueOf(d.longValue()) : String.valueOf(d);
        }
        if (value instanceof Number n) {
            return String.valueOf(n);
        }
        return String.valueOf(value);
    }

    private static String normalizeLabel(String raw) {
        if (raw == null || raw.isBlank()) {
            return "Formula";
        }
        String s = raw.trim();
        String lower = s.toLowerCase(Locale.ROOT);
        if ("formula".equals(lower) || "方剂".equals(s) || "方".equals(s)) {
            return "Formula";
        }
        if ("herb".equals(lower) || "药味".equals(s) || "药".equals(s)) {
            return "Herb";
        }
        throw new IllegalArgumentException("label 只支持 Formula/方剂 或 Herb/药味，收到：" + raw);
    }

    private static Set<String> parseTypes(String raw) {
        Set<String> types = new LinkedHashSet<>();
        if (raw == null || raw.isBlank()) {
            types.add("Formula");
            types.add("Herb");
            return types;
        }
        for (String part : splitCsv(raw)) {
            types.add(normalizeLabel(part));
        }
        if (types.isEmpty()) {
            types.add("Formula");
            types.add("Herb");
        }
        return types;
    }

    /** 收集节点；同一节点被多条路径命中时保留最小跳数。 */
    private static void collect(Node n, int distance, Set<String> types, Map<String, DistNode> target) {
        DistNode existing = target.get(n.elementId());
        if (existing != null && existing.distance() <= distance) {
            return;
        }
        GraphNode vo = toNode(n);
        if (!types.contains(vo.label())) {
            return;
        }
        target.put(n.elementId(), new DistNode(n, vo, distance));
    }

    private static List<String> splitCsv(String raw) {
        List<String> out = new ArrayList<>();
        for (String part : raw.split(",")) {
            String s = part.trim();
            if (!s.isEmpty()) {
                out.add(s);
            }
        }
        return out;
    }

    private static String requireText(String raw, String field) {
        if (raw == null || raw.isBlank()) {
            throw new IllegalArgumentException(field + " 不能为空");
        }
        return raw.trim();
    }

    private static int clamp(int v, int min, int max) {
        return Math.min(Math.max(v, min), max);
    }
}
