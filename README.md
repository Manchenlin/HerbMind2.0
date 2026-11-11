# HerbMind（本草心智）· v2 重构

> 可插拔的多语料中医知识平台。首个语料《中医经典方证案例研究》，已接入《伤寒论》原文。
> 规划文档（含 `prototype/` 原型）见本仓库 [`project_plan/`](project_plan/)。
> **远端仓库**：`https://github.com/Manchenlin/HerbMind2.0.git`

## 获取代码

```bash
git clone https://github.com/Manchenlin/HerbMind2.0.git
cd HerbMind2.0
```

## 快速开始

> **组员请看 [`docs/新人上手指南.md`](docs/新人上手指南.md)**（零经验版，含常见问题）。

```bash
# 1) 起中间件（PostgreSQL / Neo4j / Redis / Nacos）
#    首次启动会自动建好 41 张表（database/pg/00→04）
docker compose -f docker/docker-compose.infra.yml up -d

# 2) 导入数据
#  ★ 组员（推荐）：用组长分发的数据快照（.sql 或 .sql.gz 均可，脚本自动识别；不进仓库、不烧云额度）
bash scripts/init-data.sh /c/Users/你/Desktop/herbmind_data.sql
#    库里已有数据要重来时加 --reset：bash scripts/init-data.sh <快照> --reset

#  ★ 仅"数据的产出者"（拥有旧库的人）才跑迁移：
#    cd database/etl && pip install -r requirements.txt && python migrate_legacy.py && python build_graph.py

# 3) 起服务（IDEA 打开 backend/pom.xml，或 bash scripts/run-dev.sh）
#    后端：svc-identity :8081 / svc-catalog :8082 / svc-search :8083 / svc-training :8084
#          svc-graph :8085 / svc-insight :8086 / herbmind-bff :8090 / herbmind-gateway :8080
#    Agent：cd agent && python run.py --reload  →  :8091（网关用 /api/agent/** 转发过来）
#    前端：cd frontend && npm i && npm run dev  →  http://localhost:5173/
```

> **数据不重复消耗**：598 条向量已随快照分发，**任何人都不需要重新调用 Embedding API**。

## 数据库（已建成 · 41 表 / 73 索引）

建库脚本 `database/pg/`（initdb 自动按序执行，全部幂等）：

| 文件 | 内容 |
|---|---|
| `00-extensions.sql` | `vector` / `pg_trgm` /（`pg_jieba` 可选，缺失则兜底 `jiebacfg`） |
| `01-schema.sql` | 语料骨架（book / book_node）+ 内容域 + 最小三域表 |
| `02-relation.sql` | 通用关系表 `relation`（跨域兜底，06 §7） |
| `03-domains.sql` | 用户域 / 练习学习域 / 图谱规则域 / Agent 域 / 治理域 + 专属关系表 |
| `04-indexes.sql` | **HNSW 向量索引** + GIN 全文 + trgm 模糊索引 |

数据（2026-11-11 实核，见 `scripts/smoke.py` 基线）：`formula=245`、`case_record=290`、`classic_quote=568`、`content_unit=598`（全含 1024 维向量）、`formula_herb=1315`、`relation=155`。
Neo4j：`Formula=245`、`Herb=376`、`COMPOSED_OF=1288`。

## 目录结构

```
HerbMind/
├── backend/            Java 17 + Spring Boot 3.3.5 / Spring Cloud 2023（Maven 多模块，10 个模块）
│   ├── herbmind-common      横切基座：R<T> / PageResult / 全局异常
│   ├── herbmind-contract    契约层：约 40 个 VO/DTO + 6 个 Feign Client（跨服务只认接口）
│   ├── svc-identity  :8081  身份域：登录注册 JWT / 收藏 / 笔记 / 讨论
│   ├── svc-catalog   :8082  内容域：目录树 / 方剂 / 医案 / 条文 / 原文单元 / 语料登记
│   ├── svc-search    :8083  检索域：向量+全文+2-gram 词项+条文 四腿召回 + RRF 融合
│   ├── svc-training  :8084  练习域：出题 / 提交 / 规则评分（药味 F1）/ 错题 / 背诵 / 盲盒
│   ├── svc-graph     :8085  图谱域：Neo4j 邻居 / 方心子图 / 相似度地图 / 路径
│   ├── svc-insight   :8086  科研统计：用药 / 证候 / 趋势 / 导出 / 研究包
│   ├── herbmind-bff  :8090  前端唯一业务入口：/api/biz/**（Feign 转发 + 分区降级 + R<T> 包装）
│   └── herbmind-gateway :8080  网关：Spring Cloud Gateway + JWT 全局过滤器
├── agent/              Python 3.11 + FastAPI :8091（域3 智能域：RAG + 工具调用 + SSE）
├── frontend/           Vue 3 + TS strict + Vite（36 个页面 / 35 条路由，无 UI 库、无图表库）
├── database/
│   ├── pg/             DDL 00→04（initdb 自动执行，全部幂等）
│   └── etl/            迁移 / 补录 / 向量 / 建图脚本（Python）
├── docker/             docker-compose.infra.yml（只起中间件，业务服务跑 IDE / 命令行）
├── test/               前端纯函数单测（vitest，32 例，测 graphLayout 与图谱错误分诊）
└── scripts/            run-dev 起后端 / smoke.py 数据冒烟 / init-data.sh 导快照 / verify-a 域1验收
```

## 平台能做什么（功能地图）

前端 36 个页面分三块，**全部接真实接口**（治理三页仍是示意数据，见"已知缺口"）：

| 块 | 页面 | 用户拿到的价值 |
|---|---|---|
| 读 | 首页 / 书架 / 典籍浏览 / 目录节点 / 方剂 / 医案 / 条文 | 按「章→节→类→单元」读原书；节内可搜原文、调字号主题、记住读到哪、方名悬停看组成 |
| 查 | 检索工作台 / 结果分面 / 条文反向索引 / 智能问答 | 一个词同时搜方剂·医案·原文·条文，四腿召回按相关度融合；问答带引用卡与耗时 |
| 练 | 练习台 / 答题 / 评分报告 / 案例盲盒 / 背诵打卡 / 错题本 / 学习路径 / 学习档案 | 出题→作答→规则评分（药味 F1 + 辨证 + 治法）→ 错题回流→ 路径推进 |
| 研 | 科研工作台 / 数据导出 | 用药频次、证候分布、趋势，一键导出研究包 |
| 图 | 图谱探索 / 方心子图 / 相似度地图 | 方剂↔药味邻接、组成相近方、全部方剂二维相似度地图 |

## 测试与验收

```bash
python scripts/smoke.py                       # 数据冒烟：11 项（表行数 / 向量覆盖 / BFF / Neo4j）
cd agent && python -m pytest tests -q         # Agent 单测：约 180 例
cd frontend && npm run build                  # = vue-tsc --noEmit && vite build（类型检查 + 打包）
cd frontend && npx vitest run --config ../test/vitest.config.mts   # 前端纯函数单测：32 例
cd backend && mvn -q -pl svc-graph test       # 后端单测：目前只有 svc-graph 有（23 例）
```

> 域1 的实现与验收细节见 [`docs/A_内容域_交付说明.md`](docs/A_内容域_交付说明.md)。

## 关键约定（详见 `../project_plan/15_团队分工与接口协作.md` 与 `09_API契约清单.md`）

- **路由分层**：`/api/biz/**` 仅 BFF；`/api/agent/**` 仅 Agent；各 svc 只暴露 `/internal/**`。
- **响应**：`R<T> = {code, msg, data}`；分页 `PageResult`。
- **命名**：JSON 用 camelCase，数据库列用 snake_case。
- **时区**：`TIMESTAMPTZ` ↔ Java `OffsetDateTime`。
- **生成列 `content_unit.search_tsv` 禁止被 ORM 映射**。
- 语料目录**唯一表 `book_node`**；检索入口**唯一表 `content_unit`**。

## 服务发现与配置（当前：静态直连，Nacos 未接）

网关的两条路由写的是**静态地址**（`http://localhost:8090`、`http://localhost:8091`），BFF 的 6 个 Feign Client 也默认 `http://localhost:8xxx`，
可用 `${herbmind.svc-*-url}` 覆盖。

Nacos 容器已在 `docker/docker-compose.infra.yml` 里起好（8848/9848），但**代码尚未接入**：`backend/` 下没有 nacos 依赖、没有 `bootstrap.yml`、
没有 `@EnableDiscoveryClient` / `@RefreshScope`。即当前既不是注册发现，也不是配置中心，纯静态直连。

这么做是刻意的取舍：单机开发阶段静态地址最省事、排错最快；注册中心的收益要等多副本/多机部署才体现。
接入时只需给 7 个服务加 nacos-discovery 依赖、把 Feign 的 `url` 换成服务名，业务代码不用改（契约层已经把 `url` 做成可覆盖属性）。

## 关于 pg_jieba（中文分词）

默认镜像 `pgvector/pgvector:pg17` **不含** pg_jieba。初始化脚本已做兜底：若未装 pg_jieba，
会自动创建一个名为 `jiebacfg` 的文本检索配置（`COPY = simple`），保证建表与查询**不报错**，
但中文分词效果有限。装好 pg_jieba 后，删掉兜底配置重建即可（见 `database/pg/00-extensions.sql` 注释）。

## 本机踩坑速查（troubleshooting）

| 现象 | 原因 | 处理 |
|---|---|---|
| 服务起在奇怪端口（如 61099）或报 `Port xxx already in use` | 宿主环境变量 `SERVER_PORT` / `SERVER__PORT` **覆盖了 yml 的 server.port** | 启动前 `unset SERVER_PORT SERVER__PORT`，或显式加 `--server.port=8082`（命令行优先级最高） |
| `mvn` 报 `ClassNotFoundException: ...classworlds.launcher.Launcher` | 本机 maven wrapper 损坏 | 用一个可用的 Maven 安装（或直接用 IDEA 内置 Maven）；`scripts/run-dev.sh` 用已打好的可执行 jar，绕开 maven |
| `docker compose up` 报容器名已存在 | 与本机其他项目重名 | 本项目容器/卷统一带 `herbmind-v2` 前缀，已隔离 |
| 跑种子报 `ModuleNotFoundError: psycopg2` | 未装依赖 | `cd database/etl && pip install -r requirements.txt` |
| 想用 `java -jar` 但 jar 不是可执行 | 父 POM 非 `spring-boot-starter-parent`，需显式绑定 `repackage` | 已在 `backend/pom.xml` 的 pluginManagement 里绑定 |
| 改了代码 `mvn package` 说成功，但 `java -jar` 报 `NoClassDefFoundError`（缺某个 contract 类） | ① 只打 `-pl svc-xxx` 时依赖从本地仓库取，contract 是旧快照；② 旧进程锁着 jar 时 `repackage` 会静默失败 | 先 `mvn -pl herbmind-contract install -DskipTests`，再 `mvn -pl svc-xxx **clean** package -DskipTests`，最后杀掉旧进程再启动 |
| `mvn install` 说成功，却在 `C:\Users\<你>\.m2` 找不到 | 本机 Maven 本地仓库被 IDEA 改到了 `D:\software\IDEA\IntelliJ IDEA 2025.3.3\mvn_repo` | 用 `mvn help:evaluate -Dexpression=settings.localRepository -DforceStdout` 确认真实路径 |
| 改了 Mapper 注解里的 SQL，接口行为没变 | SQL 编译进 jar，服务还是旧进程 | `clean package` 后重启对应服务；日志重定向到 `backend/svc-*.log` |
| PowerShell 里 `cd /d D:\path` 报"找不到接受实际参数" | `cd` 是 `Set-Location` 别名，没有 `/d` | 用 `Set-Location 'D:\path'`；调 exe 用 `& 'D:\...\python.exe'` |

## 启动顺序小结

```
中间件(PG/Neo4j/Redis/Nacos) → 建表(自动) → 数据(见下) → 建图(build_graph)
   → svc-identity:8081 → svc-catalog:8082 → svc-search:8083 → svc-training:8084
   → svc-graph:8085 → svc-insight:8086 → bff:8090 → gateway:8080 → agent:8091
   → 验证：python scripts/smoke.py（11 项全绿才算起好）
```

## ETL 顺序（重建数据必须按这个顺序，否则会互相覆盖）

```
migrate_legacy.py                  # 从旧库迁 content_unit（会 TRUNCATE）
→ apply_supplement.py              # 补 formula_herb 组成
→ sync_content_unit.py             # 重算全部向量
→ merge_book_and_import_chapter1.py # 三本书合一 + 补回第一章（会重建 book_node）
→ import_docx_gap.py               # 补录 docx 里漏掉的节级正文与 2 个表格
→ build_graph.py                   # 方剂图谱
```

`import_docx_gap.py` 是按 `book_node.title` 挂接的，**任何重建 `book_node` 的脚本跑完都要重跑它**。
详细操作、验收 SQL、踩坑记录见 [`docs/A_docx正文补录操作手册.md`](docs/A_docx正文补录操作手册.md)。
