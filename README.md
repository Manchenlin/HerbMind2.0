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
#    svc-catalog :8082 → herbmind-bff :8090 → herbmind-gateway :8080
#    前端：cd frontend && npm i && npm run dev  →  http://localhost:5173/library
```

> **数据不重复消耗**：535 条向量已随快照分发，**任何人都不需要重新调用 Embedding API**。

## 数据库（已建成 · 41 表 / 73 索引）

建库脚本 `database/pg/`（initdb 自动按序执行，全部幂等）：

| 文件 | 内容 |
|---|---|
| `00-extensions.sql` | `vector` / `pg_trgm` /（`pg_jieba` 可选，缺失则兜底 `jiebacfg`） |
| `01-schema.sql` | 语料骨架（book / book_node）+ 内容域 + 最小三域表 |
| `02-relation.sql` | 通用关系表 `relation`（跨域兜底，06 §7） |
| `03-domains.sql` | 用户域 / 练习学习域 / 图谱规则域 / Agent 域 / 治理域 + 专属关系表 |
| `04-indexes.sql` | **HNSW 向量索引** + GIN 全文 + trgm 模糊索引 |

数据：`formula=245`、`case_record=290`、`classic_quote=568`、`content_unit=535`（全含 1024 维向量）、`formula_herb=1006`、`relation=155`。

## 目录结构

```
HerbMind/
├── backend/            Java 微服务（Maven 多模块）
│   ├── herbmind-common      R<T> / PageResult / 全局异常
│   ├── herbmind-contract    契约 DTO + Feign 接口
│   ├── svc-catalog          样例服务：/internal/catalog/**
│   ├── herbmind-bff         前端唯一业务入口：/api/biz/**
│   └── herbmind-gateway     网关：/api/biz/** → BFF
├── frontend/           Vue 3 + TS + Vite（视觉基线 = prototype/theme.css）
├── database/
│   ├── pg/             DDL 00→04（initdb 自动执行）
│   └── etl/            迁移 / 种子 / 建图脚本（Python）
├── docker/             docker-compose.infra.yml（中间件）
└── scripts/            smoke.py 端到端冒烟
```

## 关键约定（详见 `../project_plan/15_团队分工与接口协作.md` 与 `09_API契约清单.md`）

- **路由分层**：`/api/biz/**` 仅 BFF；`/api/agent/**` 仅 Agent；各 svc 只暴露 `/internal/**`。
- **响应**：`R<T> = {code, msg, data}`；分页 `PageResult`。
- **命名**：JSON 用 camelCase，数据库列用 snake_case。
- **时区**：`TIMESTAMPTZ` ↔ Java `OffsetDateTime`。
- **生成列 `content_unit.search_tsv` 禁止被 ORM 映射**。
- 语料目录**唯一表 `book_node`**；检索入口**唯一表 `content_unit`**。

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

## 启动顺序小结

```
中间件(PG/Neo4j/Redis/Nacos) → 建表(自动) → 种子(seed_books → import_formula) → 建图(build_graph)
                              → svc-catalog:8082 → bff:8090 → gateway:8080
                              → 验证：curl localhost:8090/api/biz/library/tree?bookId=sh
                              → 冒烟：python scripts/smoke.py
```
