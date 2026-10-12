# 07 · 知识图谱设计（Neo4j）

> 图库：Neo4j 5.x（Bolt :7687，Browser :7474）。图谱由 PostgreSQL 关系表 **ETL 派生**，不双写。
> 目的：把书中"方-证-药-症-经典-案例"的隐性关联变成**可遍历、可发现、可可视化**的知识网络。

## 1. 为什么用图数据库

- **多跳问答**：`桂枝汤 → 常见兼证 → 对应加减方`，用关系表需多次 JOIN 且难表达路径，图天然高效。
- **关系即数据**：边的类型与属性（如剂量、权重）本身就是知识。
- **可视化**：力导向图直接映射图模型，所见即所存。

## 2. 节点标签（Label）与属性

| Label | 关键属性 | 来源 |
|---|---|---|
| `:Book` | title, book_type, author, dynasty | book |
| `:Classic` | name, abbr, dynasty | classic |
| `:Chapter` | title, seq, path | book_node(node_type=chapter) |
| `:Section` | title, seq, path | book_node(node_type=section) |
| `:Category` | title, seq, path | book_node(node_type=category) |
| `:Formula` | name, alias, efficacy, page, pg_id | formula |
| `:Herb` | name, nature(四气), flavor(五味) | formula_herb 去重 |
| `:Syndrome` | name, category(六经/卫气营血…) | syndrome |
| `:Symptom` | name, type | symptom |
| `:Sign` | name, type(舌/脉) | sign |
| `:Case` | title, page, pg_id, unit_type | case_record |
| `:Quote` | article_no, content, classic | classic_quote |
| `:Treatment` | name(治法) | case_section(治法) |

## 3. 关系类型（Relationship）

| 关系 | 语义 | 属性 |
|---|---|---|
| `(:Book)-[:CONTAINS]->(:Classic\|:Section\|:Unit)` | 语料下辖内容 | — |
| `(:Classic)-[:CONTAINS]->(:Chapter)-[:CONTAINS]->(:Section)-[:HAS_CATEGORY]->(:Category)` | 书籍层级 | seq |
| `(:Section\|:Category)-[:INCLUDES]->(:Formula)` | 章节含方 | — |
| `(:Formula)-[:COMPOSED_OF]->(:Herb)` | 方-药 | dose, unit, role |
| `(:Formula)-[:INDICATES]->(:Syndrome)` | 方-证对应 | weight |
| `(:Formula)-[:MODIFIES]->(:Formula)` | 加减派生 | diff(加/减药) |
| `(:Case)-[:PRIMARY_FORMULA]->(:Formula)` | 案-主方 | — |
| `(:Case)-[:DIAGNOSED_AS]->(:Syndrome)` | 案-辨证 | — |
| `(:Case)-[:MANIFESTS]->(:Symptom\|:Sign)` | 案-症状/体征 | — |
| `(:Case)-[:CITES]->(:Quote)` | 案-引条文 | — |
| `(:Quote)-[:OF_CLASSIC]->(:Classic)` | 条文属经典 | — |
| `(:Quote)-[:CORRESPONDS]->(:Formula)` | 条文-方 | — |
| `(:Formula)-[:SIMILAR_TO]->(:Formula)` | 方相似 | score |
| `(:Symptom)-[:CO_OCCURS]->(:Symptom)` | 症共现 | weight |
| `(:Formula)-[:PREREQUISITE]->(:Formula)` | 学习先修 | — |
| `(:Treatment)-[:FOR]->(:Syndrome)` | 治法-证 | — |

> **统一本体约定（多语料）**：Label 固定为标准集——`:Book :Classic :Chapter :Section :Category :Formula :Herb :Drug :Case :Quote :Syndrome :Symptom :Sign :Treatment`，**禁止每本书自定义 Label**（避免 Label 爆炸）；共享属性统一为 `name / pg_id / book_id`。**跨书同名实体自动 `MERGE` 合并**（如"麻黄"在多本书中是同一节点）→ 天然实现跨书知识融合。

## 4. Cypher 示例

**建约束**
```cypher
CREATE CONSTRAINT formula_name IF NOT EXISTS FOR (f:Formula) REQUIRE f.name IS UNIQUE;
CREATE CONSTRAINT herb_name    IF NOT EXISTS FOR (h:Herb)    REQUIRE h.name IS UNIQUE;
CREATE INDEX formula_page IF NOT EXISTS FOR (f:Formula) ON (f.page);
```

**建节点/关系（节选）**
```cypher
MERGE (c:Classic {name:$classic})
MERGE (f:Formula {name:$name}) SET f.efficacy=$efficacy, f.page=$page, f.pg_id=$pgId
MERGE (c)-[:CONTAINS]->(f);
// 方-药
UNWIND $herbs AS h
  MERGE (hb:Herb {name:h.name})
  MERGE (f)-[r:COMPOSED_OF]->(hb) SET r.dose=h.dose, r.unit=h.unit, r.role=h.role;
```

**多跳问答：桂枝汤的常见兼证与对应加减方**
```cypher
MATCH (f:Formula {name:'桂枝汤'})-[:INDICATES]->(:Syndrome)<-[:INDICATES]-(g:Formula)
WHERE g.name <> '桂枝汤'
OPTIONAL MATCH (f)-[m:MODIFIES]->(g)
RETURN g.name AS 加减方, g.efficacy AS 功效, m.diff AS 加减
ORDER BY g.name;
```

**跨经典：同一方出现在哪些经典**
```cypher
MATCH (cl:Classic)-[:CONTAINS*]->(x)-[:INCLUDES|CORRESPONDS*0..2]->(f:Formula {name:'桂枝汤'})
RETURN DISTINCT cl.name AS 经典;
```

**学习先修路径**
```cypher
MATCH p = (a:Formula)-[:PREREQUISITE*1..4]->(b:Formula)
WHERE a.name = '麻黄汤'
RETURN p LIMIT 20;
```

**方证相似度（以药味重叠近似，或读 SIMILAR_TO）**
```cypher
MATCH (f:Formula {name:'桂枝汤'})-[s:SIMILAR_TO]->(g:Formula)
RETURN g.name, s.score ORDER BY s.score DESC LIMIT 10;
```

## 5. 图谱 ETL 派生流程

```
PG(book, classic, book_node, formula, formula_herb, case_record, case_section, classic_quote, *_rel, syndrome, symptom)
  → ETL 脚本 database/etl/build_graph.py
  → 生成节点 CSV / 批量 UNWIND
  → neo4j-admin import 或 Cypher 批量写入
  → 回写 PG 的 graph_synced 标记
```

派生规则要点：
- `formula_herb.role` 若可推导（君/臣/佐/使）则写入边属性。
- `formula_syndrome_rel` → `INDICATES`（weight 由共现频次算出）。
- 加减方：同一 `case` 下"主方"与"变方"差异药味 → `MODIFIES.diff`。
- 相似度：方剂药味集合做 Jaccard/向量相似 → `SIMILAR_TO.score`。

## 6. 与 PostgreSQL 的分工与协同

| 库 | 负责 | 理由 |
|---|---|---|
| **PostgreSQL** | 长文本、结构化、用户、练习、审计、**向量检索**、全文检索 | 事务、成熟、文本友好 |
| **Neo4j** | 关联遍历、多跳、路径、中心性、图谱可视化数据 | 图遍历快、关系即数据 |

**协同模式**：**向量定入口，图谱做扩展**
```
用户问题 → pgvector/全文召回"实体锚点"(如"桂枝汤")
        → Neo4j 取 1~2 跳邻居(兼证→加减方；条文→经典)
        → 结构化过滤 → 拼上下文交给 Agent
```

## 7. 可视化设计

- **力导向全图**：节点按 Label 着色，边按类型区分线型；支持筛选（经典/节点类型/度数）、缩放、拖拽。
- **方心子图**：以某方为中心，展开 1~2 跳。
- **相似度地图**：方剂向量降维（UMAP/t-SNE）到 2D，聚类成"方剂星系"。
- 大图降级：默认只渲染度数 Top-N，其余按需展开，避免"毛线球"。
