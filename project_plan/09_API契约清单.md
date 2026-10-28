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
| POST | `/api/agent/ask` | 问答（SSE 流式）✅ 2026-10-26 已实现 |
| POST | `/api/agent/ask/sync` | 同步问答（调试）✅ 2026-10-22 已实现 |
| GET | `/api/agent/history` | 会话列表 / 历史（**新增**） |
| POST | `/api/agent/coach` | 辨证教练 |
| POST | `/api/agent/formula/diff` | 加减**查证**（组成比对 + 引用原文；**不推断功效**，见 00 文档设计红线一） |
| POST | `/api/agent/grade` | 结构化评分（**供 BFF 编排调用**） |
| GET | `/api/agent/health` | 健康检查（白名单） |

> Agent 读后端：经 `clients/` 调各 svc 的 `/internal/**`（带 `X-User-Id`）；写：仅写自己的 `agent_*` 表。

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
| `done` | `{"conversationId":"c_61c46a22","degraded":false,"usage":{…},"illegalCitations":[]}` | 结束；`usage` 与 `illegalCitations`（**新增**） |

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

**事件顺序固定**：`tool(start)` → `tool(done)` → `citation × N` → `token × N` → `done`。
引用卡先于正文，前端可在首字出现前建好卡片表，避免角标先到、卡片后到。

**两个新增字段的用途**：
- `done.usage`：`{retrieveMs, llmMs, promptTokens, completionTokens, totalTokens}`，可直接打到调试面板。
- `done.illegalCitations`：模型编造的越界角标编号（如资料只有 5 条却写了 `[6]`）。流式下 token 已发出、正文改不了，只能回传让前端把对应角标擦掉，否则会出现"引用了一张不存在的卡"。

> ⚠️ `conversationId` 目前**只回显不落库**：`agent_conversation` / `agent_message` 表已建但为空，
> 且 `user_id` 外键指向 `app_user`，未经网关的真实用户 ID 插不进去。多轮持久化留到 M2。

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
