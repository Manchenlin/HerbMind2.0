# 09 · API 契约清单

> 统一响应：`R<T> = { code: 0, msg: "success", data: T }`。
> **路由分层（方案 A）**：`/api/biz/**` **仅 BFF**；`/api/agent/**` **仅 Agent**；各 svc 只暴露 **`/internal/**`**（服务间调用，不进网关）。
> 用户上下文由网关注入请求头 `X-User-Id / X-User-Role / X-User-Name`。
> **本文档是唯一事实源（契约）**：先改本文档 → 群内通知 → 再写代码；改契约需团队同意。

## 0. 接口文档规范（★ 新手必读）

### 0.1 统一约定

| 项 | 约定 |
|---|---|
| 响应外壳 | `R<T> = { code: 0, msg: "success", data: T }`；`code != 0` 即错误 |
| 分页 | `PageResult<T> = { list: T[], total: number, page: number, size: number }` |
| 命名 | **JSON 字段用 camelCase**；**数据库列用 snake_case**（前端只认 camelCase） |
| 时间 | ISO 8601 字符串，如 `"2026-10-12T09:30:00+08:00"` |
| ID | 字符串（如 `"f_1001"`），不用自增数字 |
| 鉴权 | 请求头 `Authorization: Bearer <token>` |
| 错误 | 顶层 `code` 非 0 为错误；HTTP 状态码同时正确（401 / 403 / 404 / 429 / 5xx） |

### 0.2 每个接口必须写全 8 项

① 路径 + 方法　② 归属域 + 负责人　③ 是否鉴权　④ **请求字段表**（字段 · 类型 · 必填 · 说明 · 示例）　⑤ **响应字段表**　⑥ 错误码　⑦ **请求示例 JSON**　⑧ **响应示例 JSON**

### 0.3 字段表模板

| 字段 | 类型 | 必填 | 说明 | 示例 |
|---|---|---|---|---|
| `sessionId` | string | 是 | 会话 ID | `"s_1001"` |

> 类型只允许：`string` / `number` / `boolean` / `object` / `T[]`（数组写元素类型）/ `enum(a,b,c)`。

## 1. Gateway（:8080）

| 路由 | 目标 | 说明 |
|---|---|---|
| `/api/biz/**` | **BFF :8090** | 前端唯一业务入口 |
| `/api/agent/**` | **Agent :8091** | 前端智能入口 |
| `/internal/**` | —— | **不进网关**（仅服务间/集群内可达） |

**免鉴权白名单**（经网关直接放行）：

| 路径 | 说明 |
|---|---|
| `/api/biz/user/login` | 登录（由 BFF 转发至 svc-identity） |
| `/api/biz/user/register` | 注册（同上） |
| `/api/agent/health` | Agent 健康检查 |

## 2. BFF —— 前端唯一入口（:8090，`/api/biz/**`） · 集成负责人：域2（代码三人共享）

BFF 是**前端所有请求的落点**，按页面聚合各 svc 的 `/internal/**`。

> **归属规则**：BFF 是**三人共享的一份代码**（同一个 Git 工程），不是某一个人的私有服务——**三人都写 BFF**：域1 维护 `bff/catalog`、域2 维护 `bff/train`、域3 维护 `bff/graph`；**各域只改自己包里的文件**。域2 当**集成负责人**，只负责**合并把关 + 公共文件（pom / 启动类 / 全局异常）规范 + 组织集成**，不独占编写。

| 方法 | 路径 | 说明 | 聚合来源 |
|---|---|---|---|
| GET | `/api/biz/home` | 首页数据 | catalog + search + graph |
| POST | `/api/biz/user/register` | 注册 | identity |
| POST | `/api/biz/user/login` | 登录 → `{token, user}` | identity |
| GET | `/api/biz/user/me` | 当前用户 | identity |
| GET | `/api/biz/catalog/books` | 书架 / 语料列表 | catalog |
| POST | `/api/biz/catalog/import` | 导入语料（UGC） | catalog + governance |
| GET | `/api/biz/catalog/import/{id}` | 导入状态 / 解析结果 | catalog |
| GET | `/api/biz/library/tree` | 典籍目录树（book_node） | catalog |
| GET | `/api/biz/catalog/node/{id}` | 目录节点（经典/章/节/类） | catalog |
| GET | `/api/biz/formula/{id}/page` | 方剂详情页数据 | catalog + graph + identity |
| GET | `/api/biz/case/{id}/page` | 案例详情页数据 | catalog + identity |
| GET | `/api/biz/quote/{id}/page` | 条文详情页数据 | catalog + graph |
| GET | `/api/biz/search` | 检索（分面） | search |
| POST | `/api/biz/search/semantic` | 语义检索（混合召回） | search |
| GET | `/api/biz/search/quote-index` | 条文反向索引 | search |
| GET | `/api/biz/search/facets` | 分面统计 | search |
| GET | `/api/biz/train/unit/{ref}` | 练习题面（藏答案） | training + catalog |
| POST | `/api/biz/train/session` | 开练习会话 | training |
| GET | `/api/biz/train/session/{id}` | 会话题面 | training |
| POST | `/api/biz/train/answer` | 提交作答 → 评分（**BFF 编排**：存答案→Agent 评分→落分） | training + agent |
| GET | `/api/biz/train/report/{id}` | 评分报告 | training |
| POST | `/api/biz/train/blindbox` | 随机盲盒题 | training |
| GET | `/api/biz/train/recite/due` | 待复习条文（SRS） | training |
| GET | `/api/biz/graph/subgraph` | 子图（按实体/筛选） | graph |
| GET | `/api/biz/graph/formula/{id}` | 方心子图 | graph |
| GET | `/api/biz/graph/path` | 两实体间路径 | graph |
| GET | `/api/biz/graph/map` | 相似度地图坐标数据 | graph |
| GET | `/api/biz/me/dashboard` | 个人总览 | training + identity |
| GET | `/api/biz/me/profile` | 学习档案 / 雷达 | training |
| GET | `/api/biz/me/wrong` | 错题本 | training |
| GET | `/api/biz/me/path` | 学习路径 | training |
| POST | `/api/biz/user/favorite` | 加 / 取消收藏 | identity |
| GET | `/api/biz/user/favorites` | 收藏列表 | identity |
| POST | `/api/biz/user/note` | 写笔记 | identity |
| GET | `/api/biz/user/notes` | 笔记列表 | identity |
| GET/POST | `/api/biz/discuss` | 讨论主题 / 楼层 | identity |
| GET | `/api/biz/insight/herbs` | 用药频次 Top-N | insight |
| GET | `/api/biz/insight/syndrome` | 证候分布 | insight |
| GET | `/api/biz/insight/trend` | 经典 / 章节分布 | insight |
| GET | `/api/biz/insight/export` | 导出（csv/json/graphml） | insight |
| POST | `/api/biz/insight/research-pack` | 可复现研究包 | insight |
| GET | `/api/biz/admin/overview` | 治理总览 | governance + insight |
| GET | `/api/biz/admin/review/pending` | 待复核 | governance |
| POST | `/api/biz/admin/review` | 提交复核 | governance |
| GET | `/api/biz/admin/issues` | OCR 疑点清单 | governance |
| GET | `/api/biz/admin/audit` | 审计日志 | governance |

## 3. svc-identity —— 内部（:8081，`/internal/identity/**`） · 域2

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/internal/identity/user/register` | 注册 |
| POST | `/internal/identity/user/login` | 登录 → `{token, user}` |
| GET | `/internal/identity/user/me` | 当前用户 |
| POST | `/internal/identity/favorite` | 加 / 取消收藏 |
| GET | `/internal/identity/favorites` | 收藏列表 |
| POST | `/internal/identity/note` | 写笔记 |
| GET | `/internal/identity/notes` | 笔记列表 |
| GET/POST | `/internal/identity/discuss` | 讨论主题 / 楼层 |

## 4. svc-catalog —— 内部（:8082，`/internal/catalog/**`） · 域1

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/internal/catalog/books` | 语料（书架）列表 |
| POST | `/internal/catalog/import` | 导入语料（UGC） |
| GET | `/internal/catalog/import/{id}` | 导入状态 / 解析结果 |
| GET | `/internal/catalog/tree` | 目录树（book_node） |
| GET | `/internal/catalog/node/{id}` | 目录节点（**替代原 chapter 端点**） |
| GET | `/internal/catalog/formula/{id}` | 方剂详情 |
| GET | `/internal/catalog/case/{id}` | 案例详情 |
| GET | `/internal/catalog/quote/{id}` | 条文详情 |
| GET | `/internal/catalog/formula/{id}/related` | 关联条文 / 案例 |
| POST | `/internal/catalog/batch` | 按 id / 名称批量取 |

## 5. svc-search —— 内部（:8083，`/internal/search/**`） · 域1

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/internal/search` | 多维 / 关键词检索（分面） |
| POST | `/internal/search/semantic` | 语义检索（混合召回） |
| POST | `/internal/search/recall` | 向量 + 全文混合召回（**供 Agent**） |
| GET | `/internal/search/quote-index` | 条文反向索引 |
| GET | `/internal/search/facets` | 分面统计 |

## 6. svc-training —— 内部（:8084，`/internal/training/**`） · 域2

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/internal/training/session` | 开练习会话 |
| GET | `/internal/training/session/{id}` | 会话题面 |
| POST | `/internal/training/answer` | 存作答 |
| POST | `/internal/training/score` | 落评分（**由 BFF 编排调用**） |
| GET | `/internal/training/report/{id}` | 评分报告 |
| POST | `/internal/training/blindbox` | 随机盲盒题 |
| GET | `/internal/training/recite/due` | 待复习条文（SRS） |
| GET | `/internal/training/profile` | 学习档案（供 Agent `get_user_profile`） |
| GET | `/internal/training/wrong` | 错题本 |
| GET | `/internal/training/path` | 学习路径 |

## 7. svc-graph —— 内部（:8085，`/internal/graph/**`） · 域3

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/internal/graph/subgraph` | 子图（按实体 / 筛选） |
| GET | `/internal/graph/formula/{id}` | 方心子图 |
| GET | `/internal/graph/neighbors` | 邻居子图（供 Agent） |
| GET | `/internal/graph/path` | 两实体间路径 |
| GET | `/internal/graph/map` | 相似度地图坐标数据 |
| POST | `/internal/graph/query` | 受限 Cypher 查询（只读） |

## 8. svc-insight —— 内部（:8086，`/internal/insight/**`） · 域1

> **跨域读法（约定）**：insight **不直连他域表**，经 `/internal/catalog/**`、`/internal/training/**`、`/internal/search/**` 只读聚合（或读离线统计快照）。

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/internal/insight/herbs` | 用药频次 Top-N |
| GET | `/internal/insight/herb-stats` | 用药统计（供 Agent） |
| GET | `/internal/insight/syndrome` | 证候分布 |
| GET | `/internal/insight/trend` | 经典 / 章节分布 |
| GET | `/internal/insight/export` | 导出（csv/json/graphml） |
| POST | `/internal/insight/research-pack` | 可复现研究包 |

## 9. svc-governance —— 内部（:8087，`/internal/governance/**`） · 域3

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/internal/governance/overview` | 治理总览 |
| GET | `/internal/governance/review/pending` | 待复核 |
| POST | `/internal/governance/review` | 提交复核 |
| GET | `/internal/governance/issues` | OCR 疑点清单 |
| GET | `/internal/governance/audit` | 审计日志 |

## 10. herbmind-agent —— 前端智能入口（:8091，`/api/agent/**`） · 域3

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/agent/ask` | 问答（SSE 流式）✅ 2026-10-26 已实现；2026-10-31 增加工具取证轨迹 |
| POST | `/api/agent/ask/sync` | 同步问答（调试）✅ 2026-10-22 已实现；2026-10-31 增加 `toolCalls` / `conversationId` |
| GET | `/api/agent/history` | 会话列表 / 历史 ✅ 2026-10-31 已实现（见 §13.4） |
| POST | `/api/agent/coach` | 辨证教练 |
| POST | `/api/agent/formula/diff` | 加减**查证**（组成比对 + 引用原文；**不推断功效**，见 00 文档设计红线一） |
| POST | `/api/agent/grade` | 结构化评分（**供 BFF 编排调用**） |
| GET | `/api/agent/health` | 健康检查（白名单） |

> Agent 读后端：经 `clients/` 调各 svc 的 `/internal/**`（带 `X-User-Id`）；写：仅写自己的 `agent_*` 表。
>
> ✅ 2026-10-31：上述「经 `clients/` 调 `/internal`」已落地——4 个工具
> （`search_formula` / `search_case` / `semantic_recall` / `graph_neighbors`）不再直连 PG/Neo4j。
> `ask` 主链的向量检索仍直连 pgvector（口径已按 0.5 阈值 + 6:4 配额校准，本轮不动）。

## 11. 内部端点总览

各 svc 的 `/internal/**` 即上文 §3–§9；**均不进网关**，仅集群内可达（网关不配置对应路由）。

## 12. 错误码约定（示例）

| code | 含义 |
|---|---|
| 0 | 成功 |
| 400x | 参数错误 |
| 401 | 未登录 / Token 失效 |
| 403 | 无权限 |
| 404 | 资源不存在 |
| 429 | 触发限流 |
| 5xxx | 服务端错误（含 Agent 降级标记） |

## 13. 接口打样（三域各一 · 照此格式补全其余）

### 13.1 域1 · `GET /api/biz/library/tree` —— 目录树

- **归属**：域1 内容域　**负责人**：A　**鉴权**：需要
- **查询参数**

| 字段 | 类型 | 必填 | 说明 | 示例 |
|---|---|---|---|---|
| `bookId` | string | 否 | 语料 ID；不传 = 当前语料 | `"sh"` |

- **响应 `data`：`BookTreeNode[]`**

| 字段 | 类型 | 说明 | 示例 |
|---|---|---|---|
| `id` | string | 节点 ID | `"n_1"` |
| `title` | string | 标题 | `"辨太阳病脉证并治（上）"` |
| `nodeType` | enum(classic,chapter,section,category) | 节点类型 | `"chapter"` |
| `children` | BookTreeNode[] | 子节点 | `[]` |

- **错误码**：401
- **请求示例**

```
GET /api/biz/library/tree?bookId=sh
Authorization: Bearer <token>
```

- **响应示例**

```json
{
  "code": 0,
  "msg": "success",
  "data": [
    { "id": "n_1", "title": "辨太阳病脉证并治（上）", "nodeType": "chapter",
      "children": [ { "id": "n_11", "title": "太阳病提纲", "nodeType": "section", "children": [] } ] }
  ]
}
```

### 13.2 域2 · `POST /api/biz/train/answer` —— 提交作答（评分）

- **归属**：域2 成长域　**负责人**：B　**鉴权**：需要
- **请求体**

| 字段 | 类型 | 必填 | 说明 | 示例 |
|---|---|---|---|---|
| `sessionId` | string | 是 | 会话 ID | `"s_1001"` |
| `syndrome` | string | 是 | 用户辨证 | `"太阳伤寒表实证"` |
| `treatment` | string | 否 | 用户治法 | `"辛温解表，宣肺平喘"` |
| `prescription` | HerbItem[] | 是 | 药味 + 剂量 | `[{"herb":"麻黄","dose":9,"unit":"g"}]` |

> `HerbItem = { herb: string, dose: number, unit: string }`

- **响应 `data`：`AnswerScoreVO`**

| 字段 | 类型 | 说明 |
|---|---|---|
| `answerId` | string | 作答 ID |
| `total` | number | 总分（0–100） |
| `syndromeScore` | number | 辨证得分 |
| `formulaScore` | number | 方剂得分 |
| `treatmentScore` | number | 治法得分 |
| `hit` | string[] | 命中项 |
| `miss` | string[] | 遗漏项 |
| `extra` | string[] | 多余项 |
| `refText` | string | 原著对照 |

- **错误码**：400 参数错误 / 401 / 404 会话不存在
- **请求示例**

```json
{
  "sessionId": "s_1001",
  "syndrome": "太阳伤寒表实证",
  "treatment": "辛温解表，宣肺平喘",
  "prescription": [ {"herb":"麻黄","dose":9,"unit":"g"}, {"herb":"桂枝","dose":6,"unit":"g"} ]
}
```

- **响应示例**

```json
{
  "code": 0, "msg": "success",
  "data": {
    "answerId": "a_2001", "total": 82,
    "syndromeScore": 78, "formulaScore": 83, "treatmentScore": 90,
    "hit": ["恶寒","无汗","脉浮紧","身痛"], "miss": ["喘"], "extra": ["口渴"],
    "refText": "太阳伤寒表实证。治法：辛温解表，宣肺平喘。"
  }
}
```

### 13.3 域3 · `POST /api/agent/ask` —— 智能问答（SSE 流式）

- **归属**：域3 智能域　**负责人**：C　**鉴权**：需要
- **请求体**

| 字段 | 类型 | 必填 | 说明 | 示例 |
|---|---|---|---|---|
| `question` | string | 是 | 提问 | `"无汗而喘、脉浮紧用什么方？"` |
| `conversationId` | string | 否 | 续接会话 | `"c_1"` |

- **响应**：`text/event-stream`（SSE），事件类型（**实际实现，2026-10-26 已跑通**）：

| event | data 示例 | 说明 |
|---|---|---|
| `tool` | `{"name":"retrieval","status":"start"}` | 工具调用轨迹（前端渲染"工具卡"） |
| `tool` | `{"name":"retrieval","status":"done","hits":5}` | 检索结束 + 命中条数（**新增**，便于工具卡收起） |
| `citation` | `{"index":1,"id":"cu_14","refType":"formula","refId":"f_5","title":"桂枝汤","snippet":"…","score":0.64}` | 引用卡；`index` 就是正文里 `[n]` 的 n（**新增**） |
| `token` | `{"text":"无汗"}` | 逐字输出（打字机），粒度 1~4 字不等 |
| `done` | `{"conversationId":"c_ec3cb8e5_fb863bb0","degraded":false,"usage":{…},"illegalCitations":[]}` | 结束；`usage` 与 `illegalCitations`（**新增**）；`conversationId` 格式见 §13.4 备注 1 |

> 🔴 **字段名变更，前端请以此表为准（2026-10-26）**
>
> 本节初稿写的引用卡字段是 `type` / `sourceId` / `text`，但实际实现（对齐 `agent/app/schemas.py::Citation`，
> 与 `/ask/sync` 的 `citations` 用的是同一套模型）为 `refType` / `refId` / `snippet`，并多出 `title` / `score`。
>
> **映射关系**：`type → refType`、`sourceId → refId`、`text → snippet`。旧字段一律不再下发。
>
> 请求体与初稿的差异：实现复用了 `AskRequest`，因此额外接受 `topK`(1~10) 与 `refType`(`formula`/`case`)，
> 不传则走默认（方剂 60% + 医案 40% 的配额双路召回）。
>
> **限流**：已按本节错误码要求实现 429（单用户 60 秒内 20 次，单进程内存计数）。
> 另注：`X-User-Id` 是网关信任头、服务端不校验来源，因此 **8091 端口必须只允许网关访问**。

**事件顺序固定**（2026-10-31 更新，⚠️ 待三人 review）：`tool(retrieval,start)` → `tool(retrieval,done)`
→ `tool(<取证工具>,start/done)` × 0~N → `citation × N` → `token × N` → `done`。

取证工具的 `tool` 事件比原表多三个字段（只增不改，旧前端可忽略）：

| 字段 | 类型 | 说明 |
|---|---|---|
| `status` | `start` / `done` | 与原表一致 |
| `round` | int | 第几轮取证（1 起），用于前端显示"第 2 轮查证" |
| `args` | object | 仅 `start` 有；**参数值截断到 40 字**，避免工具卡撑爆/泄露整段提问 |
| `ms` / `hits` / `count` / `ok` / `hit` | int / bool | 仅 `done` 有：耗时、命中条数、是否成功、是否查到 |

引用卡仍然先于正文，前端可在首字出现前建好卡片表，避免角标先到、卡片后到。
（工具取证发生在 citation 之后、token 之前：引用卡来自 RAG 检索，此时已确定，不该被工具拖延。）

**两个新增字段的用途**：
- `done.usage`：`{retrieveMs, llmMs, promptTokens, completionTokens, totalTokens}`，可直接打到调试面板。
- `done.illegalCitations`：模型编造的越界角标编号（如资料只有 5 条却写了 `[6]`）。流式下 token 已发出、正文改不了，只能回传让前端把对应角标擦掉，否则会出现"引用了一张不存在的卡"。

> ~~⚠️ `conversationId` 目前**只回显不落库**：`agent_conversation` / `agent_message` 表已建但为空，
> 且 `user_id` 外键指向 `app_user`，未经网关的真实用户 ID 插不进去。多轮持久化留到 M2。~~（**已过期 2026-10-31**）
>
> ✅ 2026-10-31：会话已落库。每次问答在流结束后（`BackgroundTask`）写 `agent_message`(user/assistant)
> 与 `agent_tool_call`；带同一个 `conversationId` 再次提问时，读该会话最近 6 条历史作为多轮记忆
> （历史只用于理解上下文，system 里明确禁止把它当资料引用）。
> 已知限制：域2 登录链路尚未产出 `app_user`，会话暂以 `user_id=NULL` 落库，`history` 对未知用户
> 退化为"匿名会话"（详见 §13.4 备注，登录上线后自动失效）。

- **错误码**：401 / 429 限流 / 5xxx（含 degraded）
- **请求示例**

```json
{ "question": "无汗而喘、脉浮紧用什么方？" }
```

- **响应示例（SSE）**

```
event: tool
data: {"name":"search_formula","status":"start"}

event: token
data: {"text":"无汗而喘、脉浮紧属太阳伤寒表实证"}

event: citation
data: {"id":"q_35","type":"quote","sourceId":"35","page":"19","text":"太阳病，头痛发热……麻黄汤主之。"}

event: done
data: {"conversationId":"c_1","degraded":false}
```

### 13.3.1 域3 · `POST /api/agent/ask/sync` —— 同步问答的 `data` 字段

> ⚠️ 2026-10-31 新增（域3 提出，**待三人 review**）。本节是 §13.3 的姊妹篇：同一套检索/工具/提示词，只换输出方式。

- **归属**：域3 智能域　**负责人**：C　**鉴权**：需要（`X-User-Id`，缺失 401）
- **请求体**：与 §13.3 完全一致（`question` 必填；`topK` / `refType` / `conversationId` 可选）
- **响应 `data`**

| 字段 | 类型 | 说明 |
|---|---|---|
| `answer` | string | 回答正文，带 `[n]` 引用角标 |
| `citations` | Citation[] | 引用卡（`id`/`refType`/`refId`/`title`/`snippet`/`score`），与 SSE 的 `citation` 事件同源 |
| `usage` | object | `{promptTokens, completionTokens, totalTokens, retrieveMs, llmMs, toolsMs}`；**`toolsMs` 为 2026-10-31 新增**（工具取证累计耗时，0=没调工具） |
| `degraded` | bool | true=模型不可用或资料不足，`answer` 为降级内容 |
| `toolCalls` | ToolCallBrief[] | **2026-10-31 新增**。本次工具调用轨迹，按执行顺序；空数组=没有调工具 |
| `conversationId` | string | **2026-10-31 新增**。本次会话 ID；不传则生成，下一次请求带上即可续接多轮 |

`ToolCallBrief` 字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `name` | string | 工具名（`search_formula` / `search_case` / `semantic_recall` / `graph_neighbors`） |
| `args` | object | 模型给的参数，**字符串值截断到 40 字** |
| `ok` | bool | 工具是否执行成功；false=服务不可达 / 参数非法 |
| `hit` | bool | 是否查到内容；false=执行成功但库里没有 |
| `count` | int | 命中条数 |
| `ms` | int | 耗时（毫秒） |
| `error` | string | 失败原因（仅 `ok=false` 时可能非空） |

- **错误码**：401（缺 `X-User-Id`）/ 5xxx（含 degraded 降级）
- **备注**：`ok=false` 与 `hit=false` **语义不同**——前者是"没查成"，后者是"查了但没有"。
  前端展示时不要合并成一句"未找到"，否则用户会以为库里真没有。

### 13.4 域3 · `GET /api/agent/history` —— 会话列表

> ⚠️ 2026-10-31 新增（域3 提出，**待三人 review**）。

- **归属**：域3 智能域　**负责人**：C
- **数据源**：`agent_conversation` + `agent_message`（PG），单条聚合 SQL，走索引 `idx_agent_conv_user(user_id, created_at DESC)`
- **鉴权**：需要。只信网关注入的 `X-User-Id`，**缺失返回 401**；8091 不得对外暴露
- **查询参数**

| 字段 | 类型 | 必填 | 说明 | 示例 |
|---|---|---|---|---|
| `limit` | int | 否 | 返回条数，`0`（默认）=用配置 `HISTORY_LIMIT`（默认 20）；**上限 50，超出判参数错误** | `20` |

- **响应 `data`：`HistoryData`**

| 字段 | 类型 | 说明 | 示例 |
|---|---|---|---|
| `conversations` | ConversationBrief[] | 按创建时间倒序；空数组=还没有会话 | `[…]` |
| `total` | int | 本次返回的条数（不是全库总数） | `1` |

`ConversationBrief` 字段：

| 字段 | 类型 | 说明 | 示例 |
|---|---|---|---|
| `id` | string | 会话 ID，可直接作为下一次 `ask` 的 `conversationId`。格式 `c_<用户指纹8位>_<随机8位>`（指纹段是登录上线前的临时口径，见备注 1）；**客户端不要解析它**，只透传 | `"c_ec3cb8e5_fb863bb0"` |
| `title` | string | 标题（取首个问题的前 30 字） | `"无汗而喘脉浮紧用什么方"` |
| `createdAt` | string | 创建时间，ISO 8601 带时区 | `"2026-10-31T09:30:00+08:00"` |
| `messageCount` | int | 消息条数（只算 user/assistant） | `4` |
| `lastAt` | string | 最后一条消息时间；空串=还没有消息 | `"2026-10-31T09:31:12+08:00"` |

- **错误码**：401（缺 `X-User-Id`）/ 400（`limit` 越界）/ 查询失败时 **200 + 空列表**（`msg="暂无会话记录"`），不 500
- **请求示例**

```
GET /api/agent/history?limit=20
X-User-Id: u_2f1c
```

- **响应示例**

```json
{
  "code": 0,
  "msg": "success",
  "data": {
    "conversations": [
      {
        "id": "c_ec3cb8e5_fb863bb0",
        "title": "无汗而喘脉浮紧用什么方",
        "createdAt": "2026-10-31T09:30:00+08:00",
        "messageCount": 4,
        "lastAt": "2026-10-31T09:31:12+08:00"
      }
    ],
    "total": 1
  }
}
```

- **备注**
  1. **临时口径（登录上线后自动失效）**：`agent_conversation.user_id` 外键指向 `app_user`，
     而域2 登录链路尚未产出用户记录。若 `X-User-Id` 在 `app_user` 里不存在，Agent **不会**替用户系统造账号
     （绝不写 `app_user`），而是以 `user_id=NULL` 落库。
     此时 `history` 只返回**带该用户指纹的匿名会话**：会话 ID 形如 `c_<8 位指纹>_<8 位随机>`，
     指纹 = `sha1(X-User-Id)` 前 8 位。不同用户、不同电脑互相看不到对方的会话。
     域2 登录上线后此分支自动不再命中（`known_user=True` 时只查 `user_id = X-User-Id` 的会话）。
     > ~~旧口径（**已过期 2026-10-31**）：`history` 退化为返回**全库匿名会话**，
     > 多人共用部署会互相看到会话标题。~~ 已按上述指纹方案收紧。
     > 注意这是**防误看**，不是鉴权：指纹只有 32 bit 可枚举，真正的隔离靠网关 JWT + 域2 登录。
  2. 会话标题是问题前 30 字，可能含健康相关信息；前端列表页不要把它拼进日志或上报。
  3. 写库失败只 warning，不影响问答返回；因此 `messageCount` 偶尔可能比实际对话轮次少。

> 其余接口按 §0.2 的 8 项逐一补齐；本节的格式即为**模板**。

---

## 14. 域1（内容域）M2 补全 · 接口细则

> 负责人：A。本节是 §2 / §4 / §5 / §8 的**字段级补充**，不改变已有路径与语义。
> 所有 `/internal/**` 返回**裸 DTO**（不包 R）；所有 `/api/biz/**` 由 BFF 包 `R<T>`。
> 字段一律 camelCase；时间 ISO 8601；ID 为字符串。

### 14.1 `GET /api/biz/catalog/books` —— 书架 / 语料列表

- **归属**：域1　**负责人**：A　**鉴权**：需要（当前网关未开鉴权，联调期可匿名）
- **请求参数**：无
- **响应 `data`：`BookVO[]`**

| 字段 | 类型 | 说明 | 示例 |
|---|---|---|---|
| `id` | string | 语料 ID | `"bk_1"` |
| `title` | string | 书名 | `"伤寒论"` |
| `bookType` / `bookTypeLabel` | string | 类型码 / 中文 | `"fz"` / `"方证 · 医案"` |
| `author` / `dynasty` | string | 作者 / 朝代，可空 | `"张仲景"` |
| `ingestStatus` / `statusLabel` | string | 收录状态码 / 中文 | `"已发布"` |
| `createdAt` | string | ISO 时间 | `"2026-10-12T19:55:29+08:00"` |
| `unitCount` / `nodeCount` / `formulaCount` / `caseCount` | number | 条目 / 节点 / 方剂 / 医案数 | `535` |

- **错误码**：5000（数据库不可用）
- **响应示例**

```json
{ "code": 0, "msg": "success", "data": [
  { "id": "bk_1", "title": "伤寒论", "bookType": "fz", "bookTypeLabel": "方证 · 医案",
    "author": "张仲景", "dynasty": "汉", "ingestStatus": "已发布", "statusLabel": "已发布",
    "createdAt": "2026-10-12T19:55:29+08:00",
    "unitCount": 535, "nodeCount": 27, "formulaCount": 114, "caseCount": 136 } ] }
```

### 14.2 `GET /api/biz/catalog/node/{id}` —— 目录节点详情

- **归属**：域1　**负责人**：A　**鉴权**：需要
- **路径参数**：`id` string 必填，节点 ID（如 `"n_g1"`）
- **响应 `data`：`NodeDetailVO`**

| 字段 | 类型 | 说明 |
|---|---|---|
| `node` | BookTreeNode | `{id,title,nodeType,children[]}`，children 只含直接子节点 |
| `bookId` / `bookTitle` / `classicId` | string | 所属语料 / 经典 |
| `parentId` / `pathText` | string | 父节点 / 路径文本，可空 |
| `breadcrumb` | `{id,name}[]` | 从根到父级的面包屑 |
| `formulas` | `FormulaBriefVO[]` | 该节点**含所有后代节点**下的方剂 |
| `cases` | `CaseBriefVO[]` | 上述方剂关联的医案 |
| `quotes` | `QuoteRefVO[]` | 引用上述方剂的条文（最多 6 条） |
| `childCount` | number | 直接子节点数 |

`FormulaBriefVO = { id, name, efficacy, syndrome, page, nodeId, nodeTitle, herbs: HerbVO[] }`
`HerbVO = { name, dose:number, unit, role:enum(君,臣,佐,使) | null, seq }`

- **错误码**：4000（节点不存在）/ 5000
- **响应示例**

```json
{ "code": 0, "msg": "success", "data": {
  "node": { "id": "n_g1", "title": "一、太阳伤寒类方证", "nodeType": "category", "children": [] },
  "bookId": "bk_1", "bookTitle": "伤寒论", "classicId": "c_1",
  "parentId": "n_s1", "childCount": 0,
  "breadcrumb": [ {"id":"n_h1","name":"第二章《伤寒论》方证案例研究"}, {"id":"n_s1","name":"第一节 太阳病方证案例"} ],
  "formulas": [ { "id":"f_1","name":"麻黄汤","efficacy":"发汗解表，宣肺平喘","page":"19-22",
                  "herbs":[ {"name":"麻黄","dose":9,"unit":"g","role":"君","seq":1} ] } ],
  "cases": [ { "id":"cs_1","title":"麻黄汤（加味）","mainFormulaId":"f_1","page":"19" } ],
  "quotes": [ { "id":"q_1","articleNo":"35","classicName":"伤寒论","content":"太阳病……麻黄汤主之。","label":"《伤寒论》第 35 条" } ] } }
```

### 14.3 `GET /api/biz/formula/{id}/page` —— 方剂详情页数据

- **归属**：域1　**负责人**：A　**鉴权**：需要
- **响应 `data`：`FormulaVO`**

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` / `name` / `pinyin` / `alias` | string | 基本信息，pinyin/alias 可空 |
| `efficacy` / `syndrome` / `sourceText` | string | 功效 / 主治证候 / 证治归纳原文，可空 |
| `page` | string | 原书页码 |
| `nodeId` / `nodeTitle` / `chapter` | string | 所属分类 / 章 |
| `bookId` / `bookTitle` / `classicName` | string | 语料 / 经典 |
| `herbs` | HerbVO[] | 君臣佐使，按 seq |
| `quotes` | QuoteRefVO[] | 原文回顾（最多 6 条） |
| `cases` | CaseBriefVO[] | 该方主治医案 |
| `related` | FormulaBriefVO[] | 同类 / 共享药味方剂（最多 6 个） |

`QuoteRefVO = { id, articleNo, classicName, content, plainText, page, label }`
`CaseBriefVO = { id, title, mainFormulaId, mainFormulaName, syndrome, page }`

- **错误码**：4000（方剂不存在）
- **请求示例**：`GET /api/biz/formula/f_1/page`
- **响应示例**

```json
{ "code": 0, "msg": "success", "data": {
  "id": "f_1", "name": "麻黄汤", "page": "19-22", "chapter": "第一节 太阳病方证案例",
  "nodeId": "n_g1", "nodeTitle": "一、太阳伤寒类方证", "bookId": "bk_1", "classicName": "伤寒论",
  "herbs": [ {"name":"麻黄","dose":9,"unit":"g","role":"君","seq":1},
             {"name":"桂枝","dose":6,"unit":"g","role":"臣","seq":2} ],
  "quotes": [ {"id":"q_1","articleNo":"35","classicName":"伤寒论","content":"太阳病，头痛发热……麻黄汤主之。","label":"《伤寒论》第 35 条"} ],
  "cases": [ {"id":"cs_1","title":"麻黄汤（加味）","mainFormulaId":"f_1","page":"19"} ],
  "related": [ {"id":"f_2","name":"葛根汤","efficacy":"发汗解表，升津舒筋"} ] } }
```

### 14.4 `GET /api/biz/case/{id}/page` —— 医案详情页数据

- **归属**：域1　**负责人**：A　**鉴权**：需要
- **响应 `data`：`CaseVO`**

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` / `title` / `unitType` | string | 医案 ID / 标题 / 类型 |
| `mainFormulaId` / `mainFormulaName` | string | 主方 |
| `syndrome` | string | 舌脉 / 证候字段（原书 syndrome_text） |
| `page` / `bookId` / `chapter` | string | 页码 / 语料 / 章节 |
| `sections` | `{id,kind,content,seq}[]` | 栏目：`案例原文` / `按语`，content 保留换行 |
| `quotes` | QuoteRefVO[] | 该案主方的相关条文 |

- **错误码**：4000（医案不存在）
- **说明**：`案例原文` 内含「现病史 / 查体 / 辨证 / 治法 / 处方 / 治疗效果」等段落，前端按标签拆分后做「先思后看」渐进揭示。
- **响应示例**

```json
{ "code": 0, "msg": "success", "data": {
  "id": "cs_1", "title": "麻黄汤（加味）", "unitType": "case", "mainFormulaId": "f_1",
  "mainFormulaName": "麻黄汤", "page": "19", "chapter": "第一节 太阳病方证案例",
  "sections": [ { "id":"cssec_1","kind":"案例原文","seq":0,
                  "content":"徐某,男,23岁……\n现病史：发热恶寒……\n查体：……\n辨证：……\n治法：……\n处方：……" },
                { "id":"cssec_2","kind":"按语","seq":1,"content":"本案为典型太阳伤寒表实证……" } ],
  "quotes": [ {"id":"q_1","articleNo":"35","content":"太阳病……麻黄汤主之。","label":"《伤寒论》第 35 条"} ] } }
```

### 14.5 `GET /api/biz/quote/{id}/page` —— 条文详情页数据

- **归属**：域1　**负责人**：A　**鉴权**：需要
- **响应 `data`：`QuoteVO`**

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | string | classic_quote.id |
| `articleNo` / `classicId` / `classicName` | string | 单条编号（多数为空，按段落存储） |
| `content` | string | 原始整段（含多条编号原文） |
| `plainText` | string | 白话，可空（待 Agent 回填） |
| `page` / `label` | string | 页码 / 展示标题 |
| `items` | QuoteItemVO[] | 按「1.xxx(35)」正则拆出的逐条 |
| `formulas` / `cases` | `{id,name}[]` | 引用本条的方剂 / 医案（反向索引） |

`QuoteItemVO = { no, text, label, formulas:[{id,name}], cases:[{id,name}] }`

- **错误码**：4000（条文不存在）
- **响应示例**

```json
{ "code": 0, "msg": "success", "data": {
  "id": "q_1", "classicName": "伤寒论", "page": null, "label": "《伤寒论》",
  "items": [ { "no":"1","text":"太阳之为病，脉浮，头项强痛而恶寒。","label":"第 1 条",
               "formulas":[],"cases":[] },
             { "no":"35","text":"太阳病，头痛发热……麻黄汤主之。","label":"第 35 条",
               "formulas":[{"id":"f_1","name":"麻黄汤"}],"cases":[{"id":"cs_1","name":"麻黄汤（加味）"}] } ],
  "formulas": [ {"id":"f_1","name":"麻黄汤"} ],
  "cases": [ {"id":"cs_1","name":"麻黄汤（加味）"} ] } }
```

### 14.6 `GET /api/biz/search` · `POST /api/biz/search/semantic` —— 检索（混合召回）

- **归属**：域1　**负责人**：A　**鉴权**：需要
- **请求参数（GET）**

| 字段 | 类型 | 必填 | 说明 | 示例 |
|---|---|---|---|---|
| `q` | string | 是 | 关键词 / 自然语言 | `"无汗而喘、脉浮紧用什么方"` |
| `type` | enum(all,formula,case,quote) | 否 | 类型过滤 | `"formula"` |
| `bookId` | string | 否 | 语料过滤 | `"bk_1"` |
| `herb` | string | 否 | 药味过滤（如「麻黄」） | `"麻黄"` |
| `page` / `size` | number | 否 | 默认 1 / 10，size ≤ 50 | `1` / `10` |

- **请求体（POST）**：`{ "q": "...", "type": "formula", "bookId": "bk_1", "herb": "麻黄", "page": 1, "size": 10 }`
- **响应 `data`：`SearchResultVO`**

| 字段 | 类型 | 说明 |
|---|---|---|
| `list` | SearchHitVO[] | 命中列表 |
| `total` / `page` / `size` | number | 分页 |
| `mode` | enum(hybrid,fulltext,fuzzy,browse) | 实际生效的召回模式 |
| `tookMs` | number | 耗时 |
| `facets` | `{types,classics,books}` | 分面计数（`Record<string,number>`） |

`SearchHitVO = { id, refType:enum(formula,case,quote), refId, title, snippet, score:0~1, bookId, bookTitle, classic, chapter, section, page, herbs:string[], matchedBy:enum(vector,fulltext,fuzzy,quote)[], meta }`

> `title` / `section` 均为「展示用」字段：`title` 对医案回查 `case_record.title`（`content_unit.title` 存的是书名），
> `section` 取自 `meta_jsonb.section`（比 `chapter` 细一级）。`quote-index` 覆盖全部 568 行条文：
> 有「1.xxx(35)」编号的按条拆，无编号的整段作为一条。

- **召回策略**：向量（pgvector，需配置 `herbmind.embedding.url`）+ 全文（pg_jieba） + 中文词项（2-gram / 整词 ILIKE） + 条文（正则拆条），四条腿 RRF 融合；任一腿不可用只降级、不报错。
- **错误码**：4000（参数错误）/ 5000
- **响应示例**

```json
{ "code": 0, "msg": "success", "data": {
  "list": [ { "id":"cu_1","refType":"formula","refId":"f_1","title":"麻黄汤",
              "snippet":"方剂：麻黄汤 组成：麻黄、桂枝、杏仁、炙甘草……","score":0.98,
              "bookId":"bk_1","bookTitle":"伤寒论","classic":"伤寒论","page":"第19-22页",
              "herbs":["麻黄","桂枝","杏仁","炙甘草"],"matchedBy":["fuzzy","fulltext"] } ],
  "total": 16, "page": 1, "size": 10, "mode": "fulltext", "tookMs": 38,
  "facets": { "types": {"formula":3,"case":8,"quote":5}, "classics": {"伤寒论":16}, "books": {"伤寒论":16} } } }
```

### 14.7 `GET /api/biz/search/quote-index` —— 条文反向索引

- **归属**：域1　**负责人**：A　**鉴权**：需要
- **请求参数**：`q`（可空 = 全量浏览）、`bookId`、`page`(1)、`size`(20)
- **响应 `data`：`QuoteIndexResultVO`**

| 字段 | 类型 | 说明 |
|---|---|---|
| `list` | `{quoteId,classicName,articleNo,text,page,formulas:[{id,name}],cases:[{id,name}]}[]` | 逐条原文 + 引用方/案 |
| `total` / `page` / `size` | number | 分页 |

- **错误码**：5000
- **响应示例**

```json
{ "code": 0, "msg": "success", "data": {
  "list": [ { "quoteId":"q_1","classicName":"伤寒论","articleNo":"35",
              "text":"太阳病，头痛发热，身疼腰痛，骨节疼痛，恶风，无汗而喘者，麻黄汤主之。",
              "formulas":[{"id":"f_1","name":"麻黄汤"}], "cases":[{"id":"cs_1","name":"麻黄汤（加味）"}] } ],
  "total": 1520, "page": 1, "size": 20 } }
```

### 14.8 `GET /api/biz/home` —— 首页聚合

- **归属**：域1　**负责人**：A（BFF `bff/catalog` 包）　**鉴权**：需要
- **响应 `data`：`HomeVO`**

| 字段 | 类型 | 说明 |
|---|---|---|
| `stats` | `{books,nodes,formulas,cases,quotes,vectors}` | 全库统计 |
| `books` | BookVO[] | 书架 |
| `today` | FormulaVO | 今日方证（按日期确定性选取） |
| `graph` | `{nodes:[{id,type,name,level}],edges:[{source,target,rel}],formulaId}` | 图谱预览（内容域轻量版） |
| `graphSource` | string | 当前为 `"catalog-preview"`；svc-graph 就绪后可切 |
| `hotKeywords` | string[] | 热门检索词 |
| `degraded` | string[] | 本次降级的分区（如 `["stats"]`） |

- **错误码**：即使部分 svc 不可用也返回 200（`degraded` 标注），全部不可用才 5000
- **响应示例**

```json
{ "code": 0, "msg": "success", "data": {
  "stats": { "books":3,"nodes":70,"formulas":245,"cases":290,"quotes":568,"vectors":535 },
  "today": { "id":"f_1","name":"麻黄汤","herbs":[] },
  "graph": { "nodes":[{"id":"f:f_1","type":"Formula","name":"麻黄汤","level":0}],
             "edges":[{"source":"f:f_1","target":"h:麻黄","rel":"COMPOSED_OF"}],"formulaId":"f_1" },
  "graphSource": "catalog-preview",
  "hotKeywords": ["无汗而喘","太阳中风","项背强几几"],
  "degraded": [] } }
```

### 14.9 其余新增 / 补全端点（简表）

| 方法 | 路径 | 说明 | 归属 |
|---|---|---|---|
| POST | `/api/biz/catalog/import` | 导入语料（UGC）→ 落 `book` + `ingest_status=draft`，返回 `{importId,status,message}` | A |
| GET | `/api/biz/catalog/import/{id}` | 导入状态（解析/向量化由 ETL 回写） | A |
| GET | `/api/biz/search/facets?q=` | 仅要分面时使用，返回 `{types,classics,books}` | A |
| GET | `/api/biz/insight/herbs?limit=` | 用药频次 Top-N：`[{herb,count,formulaCount,ratio}]` | A |
| GET | `/api/biz/insight/syndrome?limit=` | 证候分布（按目录「类方证」节点） | A |
| GET | `/api/biz/insight/trend` | 经典 / 章节分布 + 总量 | A |
| GET | `/api/biz/insight/export?format=csv\|json&kind=herbs\|formulas\|quotes\|units` | 直接回文件流（`Content-Disposition`） | A |
| POST | `/api/biz/insight/research-pack` | 可复现研究包（seed + 数据指纹 + 内联表） | A |
| GET | `/internal/catalog/daily` | 今日方证（供 BFF 首页） | A |
| GET | `/internal/catalog/graph-preview` | 图谱预览 | A |
| GET | `/internal/catalog/stats` | 全库统计 | A |
| POST | `/internal/catalog/batch` | 按 id / 名称批量取方剂摘要（**供域2 练习题面**） | A |
| GET | `/internal/catalog/formula/{id}/related` | 关联方剂（09 §4 已列出） | A |
| GET | `/internal/catalog/quote/list` | **条文列表（17 号手册 A1）**：`q` / `bookId` / `classicId` + 分页 → `{list,total,page,size}` | A |
| POST | `/internal/search/recall` | 向量 + 全文混合召回（**供 Agent**） | A |
| GET | `/internal/insight/herb-stats` | 用药统计（**供 Agent**） | A |

> `content_unit` 的 `embedding` 由 ETL 一次性写入；`svc-search` 只对**查询**调用 embedding（`HERBMIND_EMBEDDING_URL`），未配置即自动降级为全文/词项召回。

---

## 15. 域3 M2 补全 · 图谱 BFF 接口细则（`/api/biz/graph/**`）

> **归属分工**：契约字段由**域3（C）**定义；BFF 端点由**域2（B）** 在 `herbmind-bff` 的 `bff/graph` 包内实现；后端数据由域3 的 `svc-graph`（`/internal/graph/**`）提供。
> 本节字段是**冻结口径**，改动需三人 review（`15_团队分工与接口协作.md` §44-50）。
>
> **图数据现状（`[实核 2026-10-28]`）**：只有 `Formula{id,name,syndrome,page}` 与 `Herb{name}` 两类节点、
> `COMPOSED_OF{dose,unit,role}` 一类边；**没有 Syndrome / Symptom / Quote 节点**（`syndrome`、`symptom` 两表各 0 行）。
> 因此下列接口一律**只接受 `Formula` / `Herb` 两种标签**，收到别的标签返回 4000，不做"猜你想查什么"。
>
> ⚠️ **ID 口径（硬约定）**：对外一律用**稳定业务 ID** —— 方剂 `f_1`、药味 `h_麻黄`（`h:` + 药名）。
> **禁止直接暴露 Neo4j 的 `elementId`**：重建库或重启后它会变，前端收藏、URL 分享、缓存都会失效。
> 当前 `svc-graph` 返回的是 `elementId`，属域3 待改项。
>
> **错误码**：`4000` 参数错误（标签不支持、跳数越界）、`4040` 实体不存在（与 §12 的 404 类对应）、`5000` 图服务不可用。
> 注意：**"查得到实体但没有邻居"不是错误**，返回 `nodes: []` + `truncated: false`。

公共对象（下文各接口复用）：

```text
GraphNodeVO = { id:string, label:enum(Formula|Herb), name:string, props:object }
    ├ Formula.props = { syndrome?:string, page?:string }
    └ Herb.props    = { }
GraphEdgeVO = { source:string, target:string, rel:"COMPOSED_OF", props:{ dose?:string, unit?:string, role?:string } }
```

### 15.1 `GET /api/biz/graph/neighbors` —— 单实体邻居（图谱探索页）

- **归属**：域3 定义 / 域2 实现 BFF　**数据源**：`svc-graph` `GET /internal/graph/neighbors`　**鉴权**：需要
- **查询参数**

| 字段 | 类型 | 必填 | 说明 | 示例 |
|---|---|---|---|---|
| `entity` | string | 是 | 实体名或业务 ID | `麻黄汤` / `f_1` |
| `label` | enum(Formula,Herb) | 否 | 默认 `Formula`；也接受中文「方剂」「药味」 | `Formula` |
| `hops` | number | 否 | 跳数 1~3，默认 1；1 跳=直接邻居（方的药味 / 含该药的方） | `1` |
| `limit` | number | 否 | 邻居上限，默认 50，最大 200 | `50` |

- **响应 `data`：`NeighborsVO`**

| 字段 | 类型 | 说明 |
|---|---|---|
| `center` | GraphNodeVO | 中心节点 |
| `nodes` | GraphNodeVO[] | 邻居节点（不含 center，按 label 再按 name 升序） |
| `edges` | GraphEdgeVO[] | 邻居与 center 之间的边 |
| `truncated` | boolean | 是否因 `limit` 截断（true 时前端提示"仅显示前 N 个"） |

- **错误码**：4000（entity 为空 / label 不支持 / hops>3）/ 4040（实体不存在）
- **响应示例**

```json
{ "code": 0, "msg": "success", "data": {
  "center": { "id": "f_1", "label": "Formula", "name": "麻黄汤", "props": { "page": "第19-22页" } },
  "nodes": [ { "id": "h_麻黄", "label": "Herb", "name": "麻黄", "props": {} },
             { "id": "h_桂枝", "label": "Herb", "name": "桂枝", "props": {} } ],
  "edges": [ { "source": "f_1", "target": "h_麻黄", "rel": "COMPOSED_OF", "props": {} },
             { "source": "f_1", "target": "h_桂枝", "rel": "COMPOSED_OF", "props": {} } ],
  "truncated": false } }
```

### 15.2 `GET /api/biz/graph/subgraph` —— 子图（多起点 / 类型筛选，供相似度地图与批量渲染）

- **归属**：域3 定义 / 域2 实现 BFF　**数据源**：`svc-graph` `GET /internal/graph/subgraph`（待实现）　**鉴权**：需要
- **与 15.1 的差别**：`neighbors` 只从**一个**实体出发、只要一层关系；`subgraph` 支持多个起点、按节点类型筛选、返回整张子图（节点+边全量），供前端一次性渲染。
- **查询参数**

| 字段 | 类型 | 必填 | 说明 | 示例 |
|---|---|---|---|---|
| `entity` | string | 否 | 起点实体，逗号分隔最多 5 个；**不传 = 全图（受 `limit` 限制）** | `麻黄汤,桂枝汤` |
| `label` | enum(Formula,Herb) | 否 | 起点标签，默认 `Formula` | `Formula` |
| `hops` | number | 否 | 1~3，默认 2 | `2` |
| `types` | string | 否 | 只要这些节点类型，逗号分隔，默认两者都要 | `Formula,Herb` |
| `limit` | number | 否 | 节点上限，默认 200，最大 500 | `200` |

- **响应 `data`：`SubgraphVO`**

| 字段 | 类型 | 说明 |
|---|---|---|
| `nodes` | GraphNodeVO[] | 子图节点 |
| `edges` | GraphEdgeVO[] | 子图边（两端都必须出现在 `nodes` 里） |
| `stats` | `{nodeCount,edgeCount}` | 规模，便于前端决定是否开启力导向布局 |
| `truncated` | boolean | 是否截断 |

- **错误码**：4000 / 4040（`entity` 全部不存在时）
- **性能约束**：`hops=3` + `limit=500` 时服务端响应应 ≤ 1s（当前图 245 方 / 376 药 / 1288 边，属小图）

### 15.3 `GET /api/biz/graph/formula/{id}` —— 方心子图（方剂详情页 / 图谱页中心块）

- **归属**：域3 定义 / 域2 实现 BFF　**数据源**：`svc-graph` `GET /internal/graph/formula/{id}`（待实现），药味顺序与关联方取 PG（`formula_herb`）　**鉴权**：需要
- **路径参数**：`id` = 方剂 ID（`f_1`）
- **响应 `data`：`FormulaGraphVO`**

| 字段 | 类型 | 说明 |
|---|---|---|
| `center` | `{id,name,alias,syndromeText,page}` | 中心方剂（`syndromeText` 为语料原文摘录） |
| `herbs` | `{id,name,seq,dose,unit,role}[]` | 药味，`seq` 为库内顺序；`dose/unit/role` 多数为空（库内仅 69/1315 有剂量） |
| `herbsIncomplete` | boolean | true = 该方在库内药味缺失或含疑似解析残留（脏药名），前端需提示 |
| `relatedFormulas` | `{id,name,sharedHerbs:string[],jaccard:number}[]` | 与该方药味交集最大的成方，**按 Jaccard 降序、最多 5 条** |
| `notice` | string | 免责声明（不推断功效、不给处方建议） |

- **红线约束**：`relatedFormulas` 只能用**药味集合 Jaccard** 计算（规则，非模型推断）；每条必须能被前端标注为「组成相近 ≠ 同一方」
- **错误码**：4040（方剂不存在）
- **响应示例**

```json
{ "code": 0, "msg": "success", "data": {
  "center": { "id":"f_1", "name":"麻黄汤", "alias":"", "syndromeText":"恶风寒、发热，头身疼痛……脉浮紧", "page":"第19-22页" },
  "herbs": [ { "id":"h_麻黄","name":"麻黄","seq":1,"dose":null,"unit":null,"role":null },
             { "id":"h_桂枝","name":"桂枝","seq":2,"dose":null,"unit":null,"role":null } ],
  "herbsIncomplete": false,
  "relatedFormulas": [ { "id":"f_2","name":"葛根汤","sharedHerbs":["麻黄","桂枝","甘草"],"jaccard":0.625 } ],
  "notice": "仅比对药味组成，不比对剂量与配伍关系；「组成相同」不等于「是同一方」，不构成处方建议。" } }
```

### 15.4 `GET /api/biz/graph/path` —— 两实体之间的路径

- **归属**：域3 定义 / 域2 实现 BFF　**数据源**：`svc-graph` `GET /internal/graph/path`（待实现）　**鉴权**：需要
- **查询参数**

| 字段 | 类型 | 必填 | 说明 | 示例 |
|---|---|---|---|---|
| `from` | string | 是 | 起点（名称或业务 ID） | `f_1` |
| `to` | string | 是 | 终点 | `f_22` |
| `maxHops` | number | 否 | 1~4，默认 3 | `3` |
| `limit` | number | 否 | 最多返回几条路径，默认 3，最大 5 | `3` |

- **响应 `data`：`PathVO`**

| 字段 | 类型 | 说明 |
|---|---|---|
| `found` | boolean | 是否找到路径；**false 不是错误**，前端显示"两实体之间最多 N 跳内无关联" |
| `paths` | `{nodes:GraphNodeVO[],edges:GraphEdgeVO[],length:number}[]` | 路径按 `length` 升序 |
| `explanation` | string | 人类可读说明，如「经共享药味「桂枝」相连，2 跳」 |

- **错误码**：4000（起点/终点缺失或相同）/ 4040（任一实体不存在）
- **实现约束**：Cypher 必须带 `LIMIT` 与跳数上限，禁止无界 `[*]` 查询

### 15.5 `GET /api/biz/graph/map` —— 相似度地图坐标（相似度地图页）

- **归属**：域3 定义 / 域2 实现 BFF　**数据源**：`svc-graph` `GET /internal/graph/map`（待实现）　**鉴权**：需要
- **查询参数**：`metric`（enum(composition)，默认 `composition`）、`limit`（点数，默认 200，最大 500）、`nodeId`（可选，限定某目录节点下的方剂）
- **响应 `data`：`GraphMapVO`**

| 字段 | 类型 | 说明 |
|---|---|---|
| `metric` | enum(composition) | 距离口径，一期**只允许药味 Jaccard**（不提供"功效相似"这类推断口径） |
| `points` | `{id,label,name,x:number,y:number,cluster:string}[]` | `x/y` 已归一化到 0~1 |
| `version` | string | 计算版本（`metric + 数据指纹`），同版本必须可复现同一张图 |
| `truncated` | boolean | 是否截断 |

- **实现约束**：坐标由**服务端确定性计算**（同一 `version` 反复请求结果必须一致），前端只画点、不自行布局；否则每次刷新图形乱跳，无法用于讲解与截图

### 15.6 落地顺序（谁先做）

| 步骤 | 内容 | 负责 | 前置 |
|---|---|---|---|
| 1 | `svc-graph` 补 `/subgraph`、`/formula/{id}`、`/path`、`/map`，并把节点 `id` 从 `elementId` 换成 `f_*` / `h_*` | 域3（C） | 本契约冻结 |
| 2 | `herbmind-contract` 加 `GraphClient`（Feign，`url=${herbmind.svc-graph-url}`），BFF 加 `bff/graph` 包与 4 个端点 | 域2（B） | 步骤 1 的 `/internal` 签名 |
| 3 | 前端图谱 3 页接 `/api/biz/graph/**` | 域3（C） | 步骤 2 |
| 4 | `09` 变更记录补一行 | 三人 review | — |

> `contract` 与 BFF 均为**横切代码**，改动需三人 review（`15` §47-50）；`svc-graph` 属域3。
