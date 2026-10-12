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
| POST | `/api/agent/ask` | 问答（SSE 流式） |
| POST | `/api/agent/ask/sync` | 同步问答（调试） |
| GET | `/api/agent/history` | 会话列表 / 历史（**新增**） |
| POST | `/api/agent/coach` | 辨证教练 |
| POST | `/api/agent/formula/diff` | 加减推演 |
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

- **响应**：`text/event-stream`（SSE），事件类型：

| event | data 示例 | 说明 |
|---|---|---|
| `tool` | `{"name":"search_formula","status":"start"}` | 工具调用轨迹（前端渲染"工具卡"） |
| `token` | `{"text":"无汗"}` | 逐字输出（打字机） |
| `citation` | `{"id":"q_35","type":"quote","sourceId":"35","page":"19","text":"太阳病……"}` | 引用卡（可跳原文） |
| `done` | `{"conversationId":"c_1","degraded":false}` | 结束；`degraded=true` 表示降级回复 |

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
