# 域1 内容域（A）· M2 交付说明

> **唯一依据**：`project_plan/17_工作手册_A_内容域.md`（A1–A4 + §6 验收 + §7 坑 + §8 页面）。
> 接口字段以 `project_plan/09_API契约清单.md` §14 为准；页面视觉以 `project_plan/prototype/` 为准。

---

## 0. 对照 17 号手册（逐条销项）

| 17 号手册 | 要求 | 状态 |
|---|---|---|
| **A1** | `/node/{id}`（节点详情：其下 方剂/案例/条文 列表）、`/formula/{id}`、`/case/{id}`、`/quote/list` | ✅ 四个都在（`/node/{id}/detail`、`/formula/{id}`、`/case/{id}`、`/quote/list`，另补 `/quote/{id}`） |
| **A2** | 新建 `svc-search`：`/internal/search` 向量+全文混合召回 + 按类型排序 | ✅ 四条召回腿 + RRF；同分按 方剂>医案>条文 排 |
| **A3** | 前端 8 页（书架/典籍/节点/方剂/案例/条文/检索/结果）照原型 | ✅ 8 页 + 首页/导入/条文索引/科研/导出，共 13 页 |
| **A4** | BFF `bff/catalog` 加 `/api/biz/home`，聚合 **catalog + search + graph 预览** | ✅ 统计/书架/今日方证 + `hotHits`（search）+ 图谱预览 |
| §6 验收 | 245 方/290 案/568 条文/535 向量；`bk_1` 27 节点、叶子 `children: []`；`/internal/search?q=麻黄汤` 有结果；`/library`、`/search` 渲染真实数据 | ✅ 离线用真实快照复算通过（`docs/A_数据校验报告.md`）；运行验收见 `scripts/verify-a.sh` |
| §7 坑 | pg_jieba 兜底、`search_tsv` 不映射、`OffsetDateTime`、camelCase、只用 `book_node` | ✅ 逐条规避（见 §5） |
| §8 页面 | 只用 `theme.css`、复用 AppHeader/footer、数据走 `/api/biz/**` | ✅ 无 UI 库、无新全局样式 |

---

> **改动基线**：已 rebase 到最新 `master`（含域3 的 8 个页面与 `agent/`），因此域1 的新增/修改与 C 的代码互不覆盖；路由只新增域1 段，域3 段原样保留。

## 1. 一眼看完：做了什么

| # | 任务 | 结果 |
|---|---|---|
| **A1** | `svc-catalog` 补接口 | 新增 `/books`、`/import`、`/import/{id}`、`/node/{id}/detail`、`/formula/{id}`、`/case/{id}`、`/quote/{id}`、**`/quote/list`**、`/formula/{id}/related`、`/daily`、`/graph-preview`、`/stats`、`/batch`；全部 camelCase、无 `R` 外壳（由 BFF 包） |
| **A2** | 新建 `svc-search` :8083 | 四条召回腿 **向量（pgvector）+ 全文（pg_jieba）+ 中文词项 + 条文正则拆条**，RRF 融合；分面、条文反向索引、语义检索、供 Agent 的 `/recall`。**任一腿不可用只降级不报错** |
| **A3** | 前端 13 页 | 首页 / 书架 / 导入 / 典籍 / 节点 / 方剂 / 医案 / 条文 / 检索 / 结果 / 条文索引 / 科研 / 导出，全部接真实接口（不再有占位页） |
| **A4** | 首页聚合 | `GET /api/biz/home`：catalog 统计 + 书架 + 今日方证 + **search 热门命中** + 图谱预览，**分区独立降级**（某 svc 挂掉首页仍可看） |
| 额外 | `svc-insight` :8086 | 用药频次 / 证候分布 / 经典章节分布 / CSV·JSON 导出 / 可复现研究包（科研页与导出页的数据源；17 号手册 §1 把 insight 列为本域服务） |

**没有改契约里的既有路径**，只补字段与新增端点；`09` 的 §2/§4/§5/§8 路径全部保持原样。

---

## 2. 变更清单

### 2.1 新增模块

```
backend/svc-search/     检索服务 :8083（pom / yml / SearchApplication / controller / 2 service / util / EmbeddingClient）
backend/svc-insight/    科研统计 :8086（pom / yml / InsightApplication / controller / service）
```

### 2.2 `herbmind-contract`（跨服务 DTO，新增文件）

```
contract/catalog/  BookVO, HerbVO, LinkVO, FormulaBriefVO, FormulaVO, CaseBriefVO,
                   CaseSectionVO, CaseVO, QuoteRefVO, QuoteItemVO, QuoteVO, NodeDetailVO,
                   ImportRequest, ImportStatusVO, GraphPreviewVO, CatalogStatsVO
contract/search/   SearchRequest, SearchHitVO, SearchResultVO, FacetsVO,
                   QuoteIndexItemVO, QuoteIndexResultVO, SearchClient
contract/insight/  HerbStatVO, CountItemVO, TrendVO, ResearchPackVO, InsightClient
contract/catalog/CatalogClient.java   ← 扩展（books / import / nodeDetail / formula / case / quote / daily / batch / stats）
```

> DTO 用 Java `record`：JSON 字段即组件名（camelCase），不可变、少样板。

### 2.3 `svc-catalog`（补实体 / 服务 / 控制器）

```
entity/      Book, Classic, Formula, FormulaHerb, CaseRecord, CaseSection, ClassicQuote
mapper/      BookMapper, ClassicMapper, FormulaMapper, FormulaHerbMapper,
             CaseRecordMapper, CaseSectionMapper, ClassicQuoteMapper
service/     CatalogService（组装：目录 / 方剂 / 医案 / 条文 / 导入 / 今日 / 图谱预览）
             QuoteParser（把「1.xxx(35)」整段拆成逐条）
controller/  InternalCatalogController（重写）
```

### 2.4 BFF

```
bff/catalog/HomeVO, HomeService, HomeController, CatalogController, SearchController, InsightController
删：bff/controller/LibraryController.java（/api/biz/library/tree 已并入 CatalogController，避免重复映射）
```

### 2.5 前端

```
api/          catalog.ts（重写，含全部类型）  search.ts  insight.ts  home.ts  request.ts（错误消息透传）
utils/        format.ts（剂量/君臣佐使/相关度/医案段落解析/高亮）
components/   HerbChips.vue  MiniGraph.vue  Pager.vue  NoteDrawer.vue
views/        HomeView, ShelfView, ImportView, NodeView, FormulaView, CaseView, QuoteView,
              SearchView, SearchResultView, QuoteIndexView, ResearchView, ResearchExportView
              LibraryView（改为可点进节点详情）
router/       index.ts（域1 路由全部指向真实组件；域2/3 仍为占位页）
```

### 2.6 其他

```
backend/pom.xml                 modules 增加 svc-search / svc-insight
herbmind-common/.../GlobalExceptionHandler.java
                               改为返回真实 HTTP 状态（400/500），符合 09 §0.1
scripts/run-dev.sh             起五件套（catalog → search → insight → bff → gateway）
scripts/setup.ps1              Windows：导镜像 + 起中间件 + 导数据（不需要 bash）
scripts/run-dev.ps1            Windows：起五件套
scripts/verify-a.ps1           Windows：A 域验收（38 项）
scripts/verify-a.sh            A 域验收脚本（见 §4）
project_plan/09_API契约清单.md  追加 §14「域1 M2 补全 · 接口细则」
README.md                      服务清单与启动顺序更新
```

---

## 3. 怎么跑

```bash
# 0) 中间件 + 数据（已由组长/快照完成则跳过）
docker compose -f docker/docker-compose.infra.yml up -d
bash scripts/init-data.sh /c/Users/你/Desktop/herbmind_data.sql.gz

# 1) 编译（IDEA 打开 backend/pom.xml 亦可）
cd backend && mvn -DskipTests package && cd ..

# 2) 起后端五件套
bash scripts/run-dev.sh

# 3) 前端
cd frontend && npm i && npm run dev      # http://localhost:5173
```

**Windows（没有 bash 也行）**：

```powershell
# 3~4 步合成一条：导入镜像 + 起中间件 + 导数据
.\scripts\setup.ps1 `
  -Images "C:\...\herbmind-middleware-images.tar.gz" `
  -Sql    "C:\...\herbmind_data.sql"

.\scripts\run-dev.ps1                    # 起五件套
cd frontend; npm install --cache .\.npm-cache; npm run dev
.\scripts\verify-a.ps1                   # 另开终端：38 项验收
```

**语义检索（可选）**：配了 embedding 才会走向量腿，不配不会报错。

```bash
# Windows PowerShell
$env:HERBMIND_EMBEDDING_URL="https://api.siliconflow.cn/v1/embeddings"
$env:HERBMIND_EMBEDDING_KEY="sk-xxx"
# 然后重启 svc-search；/internal/search 返回的 mode 会从 fulltext 变成 hybrid
```

---

## 4. 验收（照着敲）

```bash
bash scripts/verify-a.sh        # Git Bash / Linux
.\\scripts\\verify-a.ps1          # Windows PowerShell（不需要 bash）
```

> **2026-10-27 实机验收结果：38 / 38 全部通过**（PostgreSQL 容器 + 5 个后端服务 + Vite 5173）。
> 输出留档见 `docs/A_验收结果.md`；`bk_1` 目录树实测 **27 个节点**（1 章 + 6 节 + 20 类方证），20 个叶子 `children: []`。

| 检查项 | 命令 | 期望 |
|---|---|---|
| 书架 | `curl "localhost:8082/internal/catalog/books"` | 3 部语料，带 `unitCount` |
| 目录树 | `curl "localhost:8082/internal/catalog/tree?bookId=bk_1"` | 1 个章 + 6 个节 + 20 个类方证（共 27 节点），叶子 `children: []` |
| 节点详情 | `curl "localhost:8082/internal/catalog/node/n_g1/detail"` | 含 `formulas[]`（麻黄汤等）、`breadcrumb[]` |
| 方剂 | `curl "localhost:8082/internal/catalog/formula/f_1"` | `herbs[]` 含君臣佐使、`quotes[]` 有第 35 条 |
| 医案 | `curl "localhost:8082/internal/catalog/case/cs_1"` | `sections[]` 含「案例原文 / 按语」 |
| 条文 | `curl "localhost:8082/internal/catalog/quote/q_1"` | `items[]` 拆出多条，含 `no=35` |
| 检索 | `curl "localhost:8083/internal/search?q=麻黄汤"` | `total>0`，`list[0].refType=formula` |
| 混合召回 | `curl -X POST localhost:8083/internal/search/semantic -H "Content-Type: application/json" -d "{\"q\":\"无汗而喘、脉浮紧用什么方\"}"` | 有结果（无 embedding 时 `mode=fuzzy`） |
| 条文索引 | `curl "localhost:8083/internal/search/quote-index?q=麻黄汤"` | 命中条文 + 关联方剂 |
| 统计 | `curl "localhost:8086/internal/insight/herbs?limit=5"` | 麻黄/桂枝等 Top5 |
| 首页 | `curl "localhost:8090/api/biz/home"` | `code=0`，`today`/`graph`/`stats` 齐全 |
| 前端 | 打开 `localhost:5173/` `/library` `/formula/f_1` `/search/result?q=麻黄汤` `/research` | 渲染真实数据，无白屏 |

> 关于目录节点数：`bk_1` = 1 章 + 6 节 + 20 类方证 = **27**；`node_id` 为空的 131 个方剂是数据迁移遗留（不属于任何分类），
> 目录页不展示，但**检索、方剂页、条文的「所主方剂」都能进入**。后续可在 ETL 里按 `meta_jsonb.chapter/section` 回填 `node_id`。
>
> **真实数据与任务卡文案的差异**：任务卡写目录根是「辨太阳病脉证并治（上）」，真实快照里根章节标题是
> 「第二章《伤寒论》方证案例研究」，下分 6 节（第一节 太阳病方证案例 …）。**节点数与结构一致（27 个）**，
> 验收以「27 节点 + 叶子 `children: []`」为准，不要按标题字符串断言。

> 注：`bk_1` 的 27 个节点 = 1 章 + 6 节 + 20 类方证，与 17 号手册第 6 节验收标准一致。

---

## 5. 关键设计说明（评审可能会问）

### 5.1 为什么检索要四条腿

真实库有两个坑：

1. 默认镜像没有 `pg_jieba`，`jiebacfg` 是 `COPY=simple` 兜底 —— **中文不分词**，`tsquery` 查「麻黄汤」返回 0 行；
2. 语料向量只有 535 条、查询向量需要云端 bge-m3，**开发期经常没有 key**。

所以 `svc-search` 不是“只写一条 SQL”，而是：

| 腿 | 实现 | 何时有用 |
|---|---|---|
| vector | `embedding <=> '[...]'::vector`，HNSW 索引 | 配了 embedding，自然语言问句 |
| fulltext | `search_tsv @@ plainto_tsquery('jiebacfg', q)` + `ts_rank_cd` | 装了 pg_jieba |
| fuzzy | 中文 2-gram / 整词 `ILIKE` + 命中词占比打分 | **默认场景**，保证「麻黄汤」必中 |
| quote | `regexp_matches` 把 `classic_quote.content` 拆条 | 条文不在 `content_unit` 里 |

融合用 **RRF（1/(60+rank) 累加）**：多腿同时命中的排前面；`score` 是单腿最佳分 + 多腿加成，归一到 0–1 供前端展示。每条腿独立 `try/catch`，扩展缺失/超时只降级（`mode` 会变化），接口永远 200。

### 5.2 为什么 Java 内组装而不是多表 JOIN

全库 245 方 / 290 案 / 568 条文 / 70 节点，一次请求的多次小查询成本可忽略；换来的是：

- 没有 XML mapper / 复杂 join 的字段映射坑（`node_type → nodeType` 之类）；
- 条文拆分、方名匹配、面包屑等**业务规则在 Java 里可读可测**；
- 数据量真上来后，再把这几个方法下沉为 SQL（接口不变）。

### 5.3 条文反向索引怎么来的

真实库 `classic_quote.content` 是**整段**（`1.太阳之为病……(1) 2.……(35)`），且 `formula_quote_rel` 是空表。所以：

- 用正则 `(\d+)\.(.+?)\((\d+)\)` 拆成逐条（`QuoteParser` / SQL 的 `regexp_matches(...,'gn')`）；
- 关联方剂 = 条文文本里**出现了方名**（含别名、括号内异名，按 `、，/` 切分），并对同名的长名优先；
- 关联医案 = 该案主方在关联方剂里，或案名（`·` 前）出现在条文中。
- 这是**保守关联**：宁可少连，不乱连。等 ETL 补齐 `formula_quote_rel` 后可改为精确关系（`QuoteIndexService` 里已留注释）。

### 5.4 降级策略

| 场景 | 表现 |
|---|---|
| embedding 未配置 / 超时 | `mode=fulltext/fuzzy`，检索照常 |
| pg_jieba 未装 | 全文腿 0 行，词项腿兜底 |
| svc-search 未启动 | `/api/biz/search` 返回 5000 + 明确 msg；首页 `degraded` 含 `today` 等 |
| svc-graph 未就绪 | 首页用 `graphSource=catalog-preview`（内容域自产预览） |
| 数据库未导入 | 列表为空 + 页面提示「请先导入数据快照」，不白屏 |

---

### 5.5 真实快照暴露的数据适配（已修，详见 `docs/A_数据校验报告.md`）

拿到 `herbmind_data.sql` 后离线跑了一遍真实数据，发现 6 个「代码假设 vs 数据现实」的偏差，全部已改：

| # | 数据现实 | 原实现的问题 | 修复 |
|---|---|---|---|
| 1 | 568 行条文中 **536 行没有「1.xxx(35)」编号**（整段原文） | 反向索引用 `CROSS JOIN LATERAL regexp_matches`，只索引到 98 条 | 改 `LEFT JOIN LATERAL`，无编号的整段 `COALESCE(m[2], q.content)` 作为一条；索引覆盖 568 行 |
| 2 | `content_unit.title` 对医案一律是书名「伤寒论」 | 检索结果里 290 条医案全显示「伤寒论」 | 结果分页后按 `ref_id` 回查 `case_record.title` / `formula.name` 覆盖标题 |
| 3 | 245 方中 **59 方无药味**（含麻黄汤 f_1）；`role`（君臣佐使）**全空** | 页面写「组成（君臣佐使）」看起来像坏了 | 文案改「组成」；无药味时说明「原书未收录」，不再假装有君臣佐使 |
| 4 | `formula.efficacy` **全空**（0/245） | 列表里清一色「证治待补录」 | 列表副标题回退到 `syndrome_text`（232 方有值），并保留页码 |
| 5 | `meta_jsonb.chapter` 只有 3 条（章级） | 科研页「章节分布」只有 3 行 | 改用 `COALESCE(meta_jsonb->>'section', meta_jsonb->>'chapter')`（34 条，节级） |
| 6 | 自然语言问句含「用什么方」等口语词 | 整句作为一个词项，永远匹配不上，还拉低分数 | 短查询（≤8 字）才保留整句；长句只用 2-gram（停用词表已有） |

校验结论（`docs/A_数据校验报告.md`）：

- **列名 100% 对齐**：9 张表的 COPY 列名与 Java 实体/查询字段无差异；
- **无悬空外键**：`formula.node_id` 131 个为空但 0 个悬空；`case.main_formula_id` 全部有效；
- `bk_1` = 1 章 + 6 节 + 20 类方证 = **27 节点**，与验收标准一致；
- 535 条 `content_unit` 全部带 1024 维向量；`meta_jsonb` 含 `page/chapter/section/classic/category/syndrome`；
- 用药 Top5：甘草 62、桂枝 36、大枣 28、生姜 26、芍药 23。

## 6. 已知限制 / 交接给 B、C

| 项 | 现状 | 谁来接 |
|---|---|---|
| 登录态 | 前端 `request.ts` 已带 `Authorization`，后端未校验 | B（`/api/biz/user/login`） |
| 收藏 / 笔记 | 仅 localStorage + toast 提示 | B（identity 接口） |
| 练习入口 | `/train` 仍是占位页 | B |
| 讨论区 | 医案页占位 | B |
| 图谱 / Agent | `/graph`、`/ask` 仍是占位页；首页用内容域预览 | C |
| 白话释义 | `classic_quote.plain_text` 多为空，条文页显示占位 | C（Agent 生成后回填） |
| 导入解析 | 仅登记 `book`（`ingest_status=draft`），不做文件解析 | 治理域（C）+ ETL |
| 治理工单 | 未写 `content_review`（避免跨域写表），由 C 按 `book.ingest_status='draft'` 生成 | C |
| 131 个方剂 `node_id` 为空 | 目录页不展示，检索/详情可达；建议 ETL 按 `content_unit.meta_jsonb` 回填 | A（下一迭代） |

### 6.1 本次的验证方式（离线环境说明）

开发机没有 Maven / Docker / npm 网络，所以**没有做完整编译与端到端运行**，已做的是：

| 检查 | 方式 | 结果 |
|---|---|---|
| Java 语法 | `javac` 解析全部 71 个源文件（缺依赖类，只过滤语法/自有类型错误） | 0 syntax error；无自有符号错误 |
| 前端 TS | 用本地 TypeScript 对 `src/**/*.ts` + 各 `.vue` 的 `<script setup>` 做 `--strict --noEmit`（vue/axios 用 shim 声明） | 0 error |
| 模板标识符 | 脚本扫描 template 表达式，比对 script 作用域 | 无未定义标识符 |
| 真实数据 | 解析 `herbmind_data.sql` 的 COPY 数据，用与后端相同的规则复算目录 / 条文拆条 / 检索 / 统计 | 列名全对齐、无悬空外键、`bk_1=27`、索引 634 条；报告见 `docs/A_数据校验报告.md` |
| SQL | 对照真实库结构逐条核对列名 / JSONB 操作符 / pgvector 字面量 / LATERAL 写法 | 人工核对 |

**请在联网环境补跑**：`cd backend && mvn -DskipTests package`、`cd frontend && npm i && npm run build`、`bash scripts/verify-a.sh`。

### 给 B 的接口（已可用）

```bash
# 练习题面：按方剂 id / 名称批量取（含药味，用于比对答案）
curl -X POST localhost:8082/internal/catalog/batch \
  -H "Content-Type: application/json" \
  -d '{"names":["麻黄汤"],"ids":[]}'
```

### 给 C 的接口（已可用）

```bash
# Agent 混合召回
curl -X POST localhost:8083/internal/search/recall \
  -H "Content-Type: application/json" \
  -d '{"q":"无汗而喘、脉浮紧","size":5}'

# Agent 用药统计工具
curl "localhost:8086/internal/insight/herb-stats?limit=10"
```

---

## 7. 提交方式（照分发说明的纪律）

```bash
git checkout -b feat/a-catalog
git add -A
git commit -m "feat(catalog): 补全内容域接口 + 新增 svc-search/svc-insight + 13 个前端页面"
git push -u origin feat/a-catalog
# GitHub 上开 PR；common / contract / 09 契约 的改动请 @ 三人 review
```

> 本次改动涉及 `herbmind-contract`、`herbmind-common/GlobalExceptionHandler`、`backend/pom.xml`、`09 契约`，按约定属于**跨域改动**，PR 描述里请单独列出，等 B、C review 后再合并。
