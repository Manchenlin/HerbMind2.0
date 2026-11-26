# 接口契约（生成物）

> **本文件由脚本生成，自动区不要手改。** 生成器：`project_plan/10_api_contract/gen_contract.py`；
> 重新生成：`python project_plan/10_api_contract/gen_contract.py`。
> 每个端点下的**手写区**（`HAND:BEGIN 方法 路径` 与 `HAND:END` 两条注释之间）会被原样保留，可以放心编辑。

<!-- SOURCE_HASH: 9f96fd14c9f27bd4 -->

## 事实源与权威边界

| 内容 | 权威在哪 | 冲突时改哪边 |
|---|---|---|
| 有哪些端点、如何分组、端点职责 | `thinkForProject/docs/05` §10.3（本文件共投影 51 个方法） | 改 `docs/05`，然后重跑本脚本 |
| 每条需求由哪些端点覆盖 | `thinkForProject/track/02_需求到端点.csv` | 改边表 |
| 请求／响应字段、错误码细节 | **本文件的手写区** | 改本文件；`docs/05` 只定义 §10.4 的 3 个关键接口 |
| 端点必须满足的规则类约束 | 边表 `coverage=rule` 的行 | 改边表 |

本文件**不是**第二份端点表：自动区的内容全部来自上面两个文件，没有新增事实。
曾经存在的 `project_plan/09_API契约清单.md` 之所以作废，是因为它手写维护、与设计文档各自演进；
本文件用生成 + 手写分区来避免同一个问题。

## 全局约束（不属于单个端点）

| 编号 | 约束 | 说明 |
|---|---|---|
| FR-507 | 密钥只在服务端配置，无接口暴露 | 见 `docs/03` §5 |
| FR-607 | 无自动合并逻辑，代码审查项 | 见 `docs/03` §5 |
| FR-704 | 数据表不含患者信息字段，建模约束 | 见 `docs/03` §5 |
| FR-801 | 全部 /api/admin/** 前缀统一角色拦截 | 见 `docs/03` §5 |

全局约束由代码审查或横切测试保证，不挂在单个端点上。`FR-801`（`/api/admin/**` 统一角色拦截）
虽也是全局约束，但作用于整棵前缀树，验收用越权用例矩阵覆盖。

## 鉴权与会话（UC-15、UC-16）

### `POST /api/app/auth/login`

小程序 `code` 换令牌；首次登录自动建用户

- **覆盖需求**：`FR-701`

<!-- HAND:BEGIN POST /api/app/auth/login -->
#### 请求

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|

#### 响应 `data`

| 字段 | 类型 | 说明 |
|---|---|---|
<!-- HAND:END -->

### `POST /api/app/auth/bind`

用 PC 端显示的 6 位绑定码把小程序账号并入 PC 账号

- **覆盖需求**：`FR-701`

<!-- HAND:BEGIN POST /api/app/auth/bind -->
#### 请求

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|

#### 响应 `data`

| 字段 | 类型 | 说明 |
|---|---|---|
<!-- HAND:END -->

### `GET /api/app/auth/me`

当前用户、角色、已绑定端

- **覆盖需求**：`FR-701`

<!-- HAND:BEGIN GET /api/app/auth/me -->
#### 请求

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|

#### 响应 `data`

| 字段 | 类型 | 说明 |
|---|---|---|
<!-- HAND:END -->

### `POST /api/admin/auth/login`

管理员账号密码登录

- **覆盖需求**：`FR-808`

<!-- HAND:BEGIN POST /api/admin/auth/login -->
#### 请求

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|

#### 响应 `data`

| 字段 | 类型 | 说明 |
|---|---|---|
<!-- HAND:END -->

### `POST /api/admin/auth/logout`

令牌加入吊销清单

- **覆盖需求**：`FR-808`

<!-- HAND:BEGIN POST /api/admin/auth/logout -->
#### 请求

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|

#### 响应 `data`

| 字段 | 类型 | 说明 |
|---|---|---|
<!-- HAND:END -->

### `GET /api/admin/audit-logs`

审计查询（操作人、对象、动作、时间区间）

- **覆盖需求**：`FR-120`、`FR-806`、`FR-903`

<!-- HAND:BEGIN GET /api/admin/audit-logs -->
#### 请求

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|

#### 响应 `data`

| 字段 | 类型 | 说明 |
|---|---|---|
<!-- HAND:END -->

## 书目与申请（UC-01、UC-02）

### `POST /api/app/book-applications`

学习者提交书目申请

- **覆盖需求**：`FR-101`、`FR-106`、`FR-901`
- **约束 FR-902**：检测不可用时写待检态 + 定时补偿；状态字段承载

<!-- HAND:BEGIN POST /api/app/book-applications -->
#### 请求

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|

#### 响应 `data`

| 字段 | 类型 | 说明 |
|---|---|---|
<!-- HAND:END -->

### `GET /api/app/book-applications/mine`

我的申请与状态

- **覆盖需求**：`FR-102`、`FR-106`

<!-- HAND:BEGIN GET /api/app/book-applications/mine -->
#### 请求

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|

#### 响应 `data`

| 字段 | 类型 | 说明 |
|---|---|---|
<!-- HAND:END -->

### `GET /api/admin/book-applications?status=`

申请队列

- **覆盖需求**：`FR-802`

<!-- HAND:BEGIN GET /api/admin/book-applications?status= -->
#### 请求

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|

#### 响应 `data`

| 字段 | 类型 | 说明 |
|---|---|---|
<!-- HAND:END -->

### `POST /api/admin/book-applications/{id}/approve`

通过并生成书目

- **覆盖需求**：`FR-104`、`FR-105`、`FR-802`

<!-- HAND:BEGIN POST /api/admin/book-applications/{id}/approve -->
#### 请求

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|

#### 响应 `data`

| 字段 | 类型 | 说明 |
|---|---|---|
<!-- HAND:END -->

### `POST /api/admin/book-applications/{id}/reject`

驳回，`reason` 必填

- **覆盖需求**：`FR-104`、`FR-802`

<!-- HAND:BEGIN POST /api/admin/book-applications/{id}/reject -->
#### 请求

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|

#### 响应 `data`

| 字段 | 类型 | 说明 |
|---|---|---|
<!-- HAND:END -->

### `GET /api/admin/books?status=`

书目列表

- **覆盖需求**：`FR-104`

<!-- HAND:BEGIN GET /api/admin/books?status= -->
#### 请求

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|

#### 响应 `data`

| 字段 | 类型 | 说明 |
|---|---|---|
<!-- HAND:END -->

## 导入与校对（UC-03、UC-04）

### `POST /api/admin/import-tasks`

`multipart`：底本文件 + `bookId`；返回任务号

- **覆盖需求**：`FR-103`、`FR-111`、`FR-112`、`FR-113`、`FR-114`、`FR-115`、`FR-116`、`FR-117`、`FR-122`、`FR-803`

<!-- HAND:BEGIN POST /api/admin/import-tasks -->
#### 请求

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|

#### 响应 `data`

| 字段 | 类型 | 说明 |
|---|---|---|
<!-- HAND:END -->

### `GET /api/admin/import-tasks/{id}`

状态、环节、进度计数

- **覆盖需求**：`FR-803`

<!-- HAND:BEGIN GET /api/admin/import-tasks/{id} -->
#### 请求

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|

#### 响应 `data`

| 字段 | 类型 | 说明 |
|---|---|---|
<!-- HAND:END -->

### `POST /api/admin/import-tasks/{id}/retry`

整批重试（先清理半成品）

- **覆盖需求**：`FR-803`

<!-- HAND:BEGIN POST /api/admin/import-tasks/{id}/retry -->
#### 请求

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|

#### 响应 `data`

| 字段 | 类型 | 说明 |
|---|---|---|
<!-- HAND:END -->

### `GET /api/admin/import-tasks/{id}/report`

导入报告（FR-118 的各项计数与门禁结论）

- **覆盖需求**：`FR-112`、`FR-113`、`FR-114`、`FR-117`、`FR-118`、`FR-122`

<!-- HAND:BEGIN GET /api/admin/import-tasks/{id}/report -->
#### 请求

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|

#### 响应 `data`

| 字段 | 类型 | 说明 |
|---|---|---|
<!-- HAND:END -->

### `GET /api/admin/import-tasks/{id}/review-items?type=&page=`

待校对项（性质未确认、实体未匹配、碰撞挂起）

- **覆盖需求**：`FR-116`、`FR-119`、`FR-804`

<!-- HAND:BEGIN GET /api/admin/import-tasks/{id}/review-items?type=&page= -->
#### 请求

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|

#### 响应 `data`

| 字段 | 类型 | 说明 |
|---|---|---|
<!-- HAND:END -->

### `POST /api/admin/import-tasks/{id}/sampling`

创建抽样复核任务：`ratio`（≥10%）、`minCount`（≥100）、按章分层（`FR-121`）

- **覆盖需求**：`FR-121`、`FR-804`

<!-- HAND:BEGIN POST /api/admin/import-tasks/{id}/sampling -->
#### 请求

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|

#### 响应 `data`

| 字段 | 类型 | 说明 |
|---|---|---|
<!-- HAND:END -->

### `GET /api/admin/import-tasks/{id}/sampling`

抽样结果：样本数、错误数、错误率、可导出（`FR-121`、`FR-804`）

- **覆盖需求**：`FR-121`、`FR-804`

<!-- HAND:BEGIN GET /api/admin/import-tasks/{id}/sampling -->
#### 请求

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|

#### 响应 `data`

| 字段 | 类型 | 说明 |
|---|---|---|
<!-- HAND:END -->

### `PATCH /api/admin/units/{id}`

修正单元（性质、所属章节、篇内序号），写修正留痕

- **覆盖需求**：`FR-115`、`FR-116`、`FR-119`、`FR-120`、`FR-804`

<!-- HAND:BEGIN PATCH /api/admin/units/{id} -->
#### 请求

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|

#### 响应 `data`

| 字段 | 类型 | 说明 |
|---|---|---|
<!-- HAND:END -->

## 阅读（UC-05）

### `GET /api/app/books`

已入库书目

- **覆盖需求**：`FR-202`

<!-- HAND:BEGIN GET /api/app/books -->
#### 请求

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|

#### 响应 `data`

| 字段 | 类型 | 说明 |
|---|---|---|
<!-- HAND:END -->

### `GET /api/app/books/{id}/chapters`

章节树（多层）

- **覆盖需求**：`FR-115`、`FR-202`

<!-- HAND:BEGIN GET /api/app/books/{id}/chapters -->
#### 请求

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|

#### 响应 `data`

| 字段 | 类型 | 说明 |
|---|---|---|
<!-- HAND:END -->

### `GET /api/app/chapters/{id}/units?page=&size=`

单元分页（默认 40）

- **覆盖需求**：`FR-201`

<!-- HAND:BEGIN GET /api/app/chapters/{id}/units?page=&size= -->
#### 请求

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|

#### 响应 `data`

| 字段 | 类型 | 说明 |
|---|---|---|
<!-- HAND:END -->

### `GET /api/app/units/{id}`

单元详情（含出处块）

- **覆盖需求**：`FR-117`、`FR-204`、`FR-209`、`FR-412`
- **约束 FR-206**：显示值直出不做转换；用逐字比对用例验证

<!-- HAND:BEGIN GET /api/app/units/{id} -->
#### 请求

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|

#### 响应 `data`

| 字段 | 类型 | 说明 |
|---|---|---|
<!-- HAND:END -->

### `PUT /api/app/progress`

记录最后阅读位置

- **覆盖需求**：`FR-203`、`FR-702`

<!-- HAND:BEGIN PUT /api/app/progress -->
#### 请求

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|

#### 响应 `data`

| 字段 | 类型 | 说明 |
|---|---|---|
<!-- HAND:END -->

## 检索（UC-06～UC-09、UC-17）

### `GET /api/app/search?q=&scope=&bookId=`

三类对象统一检索

- **覆盖需求**：`FR-209`、`FR-304`、`FR-308`、`FR-310`
- **约束 FR-307**：匹配用归一值、展示用原字；实现约束见 05 §11.3

<!-- HAND:BEGIN GET /api/app/search?q=&scope=&bookId= -->
#### 请求

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|

#### 响应 `data`

| 字段 | 类型 | 说明 |
|---|---|---|
<!-- HAND:END -->

### `GET /api/app/formulas?name=`

按方名查（同名列多书时返回分组）

- **覆盖需求**：`FR-301`、`FR-304`
- **约束 FR-307**：匹配用归一值、展示用原字；实现约束见 05 §11.3

<!-- HAND:BEGIN GET /api/app/formulas?name= -->
#### 请求

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|

#### 响应 `data`

| 字段 | 类型 | 说明 |
|---|---|---|
<!-- HAND:END -->

### `GET /api/app/formulas?herb=`

按药味反查

- **覆盖需求**：`FR-304`、`FR-305`

<!-- HAND:BEGIN GET /api/app/formulas?herb= -->
#### 请求

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|

#### 响应 `data`

| 字段 | 类型 | 说明 |
|---|---|---|
<!-- HAND:END -->

### `GET /api/app/formulas/{id}`

方剂详情（组成 + 出处条文）

- **覆盖需求**：`FR-205`、`FR-302`、`FR-303`、`FR-304`

<!-- HAND:BEGIN GET /api/app/formulas/{id} -->
#### 请求

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|

#### 响应 `data`

| 字段 | 类型 | 说明 |
|---|---|---|
<!-- HAND:END -->

### `POST /api/app/formulas/compare`

类方比较，`ids` 2～4 个

- **覆盖需求**：`FR-303`、`FR-306`

<!-- HAND:BEGIN POST /api/app/formulas/compare -->
#### 请求

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|

#### 响应 `data`

| 字段 | 类型 | 说明 |
|---|---|---|
<!-- HAND:END -->

### `GET /api/app/cases/{id}`

医案详情（所用方 + 原文）

- **覆盖需求**：`FR-304`、`FR-309`

<!-- HAND:BEGIN GET /api/app/cases/{id} -->
#### 请求

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|

#### 响应 `data`

| 字段 | 类型 | 说明 |
|---|---|---|
<!-- HAND:END -->

### `GET /api/app/cases?formulaId=`

某方的相关医案

- **覆盖需求**：`FR-304`、`FR-308`

<!-- HAND:BEGIN GET /api/app/cases?formulaId= -->
#### 请求

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|

#### 响应 `data`

| 字段 | 类型 | 说明 |
|---|---|---|
<!-- HAND:END -->

## 练习与复习（UC-10、UC-11）

### `POST /api/app/exercises`

出题：范围 + 题型 + 数量（≤20）

- **覆盖需求**：`FR-209`、`FR-401`、`FR-402`
- **约束 FR-403**：题目由结构化规则生成，同范围可复现
- **约束 FR-404**：唯一正解判定在生成阶段
- **约束 FR-406**：判据不全的实体不进题池

<!-- HAND:BEGIN POST /api/app/exercises -->
#### 请求

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|

#### 响应 `data`

| 字段 | 类型 | 说明 |
|---|---|---|
<!-- HAND:END -->

### `POST /api/app/exercises/{id}/answer`

作答，返回正误、正解、依据原文、复习条目变化

- **覆盖需求**：`FR-209`、`FR-405`、`FR-407`、`FR-409`

<!-- HAND:BEGIN POST /api/app/exercises/{id}/answer -->
#### 请求

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|

#### 响应 `data`

| 字段 | 类型 | 说明 |
|---|---|---|
<!-- HAND:END -->

### `GET /api/app/reviews/due?limit=`

今日到期条目（返回题目，不带答案）

- **覆盖需求**：`FR-409`

<!-- HAND:BEGIN GET /api/app/reviews/due?limit= -->
#### 请求

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|

#### 响应 `data`

| 字段 | 类型 | 说明 |
|---|---|---|
<!-- HAND:END -->

### `GET /api/app/reviews/summary`

今日待复习数量、连续学习天数

- **覆盖需求**：`FR-410`

<!-- HAND:BEGIN GET /api/app/reviews/summary -->
#### 请求

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|

#### 响应 `data`

| 字段 | 类型 | 说明 |
|---|---|---|
<!-- HAND:END -->

## 提问与缺口（UC-12、UC-13）

### `POST /api/app/ask`

提问，返回回答或拒答（`status` 三值）

- **覆盖需求**：`FR-501`、`FR-502`、`FR-503`、`FR-601`
- **约束 FR-504**：缺出处不得输出，响应组装校验
- **约束 FR-506**：输出过滤与提示词约束

<!-- HAND:BEGIN POST /api/app/ask -->
#### 请求

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|

#### 响应 `data`

| 字段 | 类型 | 说明 |
|---|---|---|
<!-- HAND:END -->

### `POST /api/app/gaps`

用户手动上报缺口，入队前经内容安全检测

- **覆盖需求**：`FR-602`、`FR-901`
- **约束 FR-902**：检测不可用时写待检态 + 定时补偿；状态字段承载

<!-- HAND:BEGIN POST /api/app/gaps -->
#### 请求

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|

#### 响应 `data`

| 字段 | 类型 | 说明 |
|---|---|---|
<!-- HAND:END -->

## 治理（UC-14）

### `GET /api/admin/gaps?status=&overdue=`

缺口队列，`overdue=true` 筛超 7 天

- **覆盖需求**：`FR-503`、`FR-601`、`FR-603`、`FR-805`

<!-- HAND:BEGIN GET /api/admin/gaps?status=&overdue= -->
#### 请求

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|

#### 响应 `data`

| 字段 | 类型 | 说明 |
|---|---|---|
<!-- HAND:END -->

### `GET /api/admin/conflicts?status=&overdue=`

冲突队列，`overdue=true` 筛超 7 天（`FR-606` 与缺口队列同一口径）

- **覆盖需求**：`FR-604`、`FR-605`、`FR-606`、`FR-805`

<!-- HAND:BEGIN GET /api/admin/conflicts?status=&overdue= -->
#### 请求

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|

#### 响应 `data`

| 字段 | 类型 | 说明 |
|---|---|---|
<!-- HAND:END -->

### `PATCH /api/admin/gaps/{id}`

处理结果 + 理由；不可补时理由必填

- **覆盖需求**：`FR-603`、`FR-805`

<!-- HAND:BEGIN PATCH /api/admin/gaps/{id} -->
#### 请求

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|

#### 响应 `data`

| 字段 | 类型 | 说明 |
|---|---|---|
<!-- HAND:END -->

### `PATCH /api/admin/conflicts/{id}`

处理结果 + 理由

- **覆盖需求**：`FR-605`、`FR-606`、`FR-805`

<!-- HAND:BEGIN PATCH /api/admin/conflicts/{id} -->
#### 请求

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|

#### 响应 `data`

| 字段 | 类型 | 说明 |
|---|---|---|
<!-- HAND:END -->

## 学习记录（FR-703～FR-705）

### `GET /api/app/favorites`

收藏列表／新增（`targetType` + `targetId`）

- **覆盖需求**：`FR-702`、`FR-703`

<!-- HAND:BEGIN GET /api/app/favorites -->
#### 请求

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|

#### 响应 `data`

| 字段 | 类型 | 说明 |
|---|---|---|
<!-- HAND:END -->

### `POST /api/app/favorites`

收藏列表／新增（`targetType` + `targetId`）

- **覆盖需求**：`FR-703`

<!-- HAND:BEGIN POST /api/app/favorites -->
#### 请求

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|

#### 响应 `data`

| 字段 | 类型 | 说明 |
|---|---|---|
<!-- HAND:END -->

### `DELETE /api/app/favorites/{id}`

取消收藏

- **覆盖需求**：`FR-703`

<!-- HAND:BEGIN DELETE /api/app/favorites/{id} -->
#### 请求

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|

#### 响应 `data`

| 字段 | 类型 | 说明 |
|---|---|---|
<!-- HAND:END -->

### `GET /api/app/notes`

笔记列表／新增（绑定对象）

- **覆盖需求**：`FR-702`、`FR-703`

<!-- HAND:BEGIN GET /api/app/notes -->
#### 请求

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|

#### 响应 `data`

| 字段 | 类型 | 说明 |
|---|---|---|
<!-- HAND:END -->

### `POST /api/app/notes`

笔记列表／新增（绑定对象）

- **覆盖需求**：`FR-703`

<!-- HAND:BEGIN POST /api/app/notes -->
#### 请求

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|

#### 响应 `data`

| 字段 | 类型 | 说明 |
|---|---|---|
<!-- HAND:END -->

### `PATCH /api/app/notes/{id}`

修改／删除笔记

- **覆盖需求**：`FR-703`

<!-- HAND:BEGIN PATCH /api/app/notes/{id} -->
#### 请求

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|

#### 响应 `data`

| 字段 | 类型 | 说明 |
|---|---|---|
<!-- HAND:END -->

### `DELETE /api/app/notes/{id}`

修改／删除笔记

- **覆盖需求**：`FR-703`

<!-- HAND:BEGIN DELETE /api/app/notes/{id} -->
#### 请求

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|

#### 响应 `data`

| 字段 | 类型 | 说明 |
|---|---|---|
<!-- HAND:END -->

### `GET /api/app/wrong-answers?page=`

错题簿

- **覆盖需求**：`FR-408`、`FR-412`、`FR-702`

<!-- HAND:BEGIN GET /api/app/wrong-answers?page= -->
#### 请求

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|

#### 响应 `data`

| 字段 | 类型 | 说明 |
|---|---|---|
<!-- HAND:END -->

### `DELETE /api/app/me/learning-records`

删除本人全部学习记录（进度、作答、错题、复习状态）；收藏与笔记由各自端点删除，不在此列（`FR-705`）

- **覆盖需求**：`FR-705`

<!-- HAND:BEGIN DELETE /api/app/me/learning-records -->
#### 请求

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|

#### 响应 `data`

| 字段 | 类型 | 说明 |
|---|---|---|
<!-- HAND:END -->

## 变更记录

| 日期 | 变更 |
|---|---|
| 2026-11-26 | 首次生成。骨架来自 `docs/05` v0.10 §10.3 与边表（82 条需求），手写字段区留空待补。 |
