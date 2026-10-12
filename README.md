# HerbMind（本草心智）· v2 重构

> 可插拔的多语料中医知识平台。首个语料《中医经典方证案例研究》，已接入《伤寒论》原文。
> 规划文档见同级目录 `../project_plan/`。

## 快速开始（三条命令）

```bash
# 1) 起中间件（PostgreSQL / Neo4j / Redis / Nacos）
docker compose -f docker/docker-compose.infra.yml up -d

# 2) 建表 + 灌种子（脚本见 database/）
#    PG 初始化脚本已在首次启动时自动执行（挂载到 initdb）；种子需手动跑一次：
cd database/etl && pip install -r requirements.txt && python seed_books.py && python import_formula.py

# 3) 起服务（IDEA 打开 backend/pom.xml，或命令行）
#    svc-catalog :8082 → herbmind-bff :8090 → herbmind-gateway :8080
#    前端：cd frontend && npm i && npm run dev
```

## 目录结构

```
HerbMind/
├── backend/            Java 微服务（Maven 多模块）
│   ├── herbmind-common      R<T> / PageResult / 全局异常
│   ├── herbmind-contract    契约 DTO + Feign 接口
│   ├── svc-catalog          样例服务：/internal/catalog/**
│   ├── herbmind-bff         前端唯一业务入口：/api/biz/**
│   └── herbmind-gateway     网关：/api/biz/** → BFF
├── frontend/           Vue 3 + TS + Vite
├── database/
│   ├── pg/             DDL + 扩展（initdb 自动执行）
│   └── etl/            语料导入 / 向量化 / 建图脚本（Python）
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
