# 13 · HTML 原型说明与页面地图

> 原型位置：`prototype/`（纯静态，双击 `index.html` 即可浏览，无需后端）。
> 视觉：现代极简（见 [04](04_视觉设计规范.md)）；交互：页面转场 + 微交互（`assets/app.js`）。
> 资源：`assets/theme.css`（设计 token + 组件）、`assets/app.js`（转场/微交互）、`assets/mock.js`（示例数据）。

## 1. 原型页面清单

| 文件 | 页面 | 对应模块 |
|---|---|---|
| `index.html` | 首页 | 入口 |
| `login.html` | 登录 / 注册 | 通用 |
| `shelf.html` | 书架 · 语料库（多语料 + 切书） | 语料库（插拔式） |
| `import.html` | 导入语料（UGC：上传 + 元信息 + 解析选项） | 语料库（插拔式） |
| `library.html` | 典籍浏览（目录树，可切书） | M2 |
| `search.html` | 检索工作台 | M1 |
| `search-result.html` | 结果分面 | M1 |
| `formula.html` | 方剂详情 | M2 |
| `case.html` | 案例详情 | M2 |
| `quote.html` | 条文详情 | M2 |
| `train.html` | 练习台 | M3 |
| `answer.html` | 答题面板 | M3 |
| `report.html` | 评分报告 | M3 |
| `blindbox.html` | 案例盲盒 | M3 |
| `graph.html` | 知识图谱探索 | M6 |
| `graph-map.html` | 方证相似度地图 | M6 |
| `ask.html` | 智能问答（工具轨迹 + 引用） | M7 |
| `me.html` | 个人中心总览 | M4 |
| `profile.html` | 学习档案（能力雷达） | M4 |
| `favorites.html` | 收藏 · 笔记 | M5 |
| `admin.html` | 治理后台 | M8 |

（共 21 页；覆盖 M1–M8 主功能 + 语料库〔插拔式〕 + 登录。）

## 2. 页面地图（跳转关系）

```
                    index.html（首页）
                          │
     ┌────────┬───────────┼──────────┬──────────┬────────────┐
     ▼        ▼           ▼          ▼          ▼            ▼
 shelf.html search.html library.html train.html graph.html  ask.html
  书架·语料    │           │          │          │            │
              ▼           ▼          ▼          ▼            ▼
        search-result formula.html answer.html graph-map  （引用卡→原文）
                        │          │
                        ▼          ▼
                     case.html   report.html
                        │          │
                        ▼          ▼
                     quote.html  blindbox.html

   me.html ── profile.html / favorites.html
   admin.html（治理）

   login.html（登录 / 注册）──▶ index.html（首页）
   shelf.html ──▶ import.html（导入语料，UGC）
```

## 3. 交互与动效说明（原型中可体验）

| 位置 | 交互 |
|---|---|
| 全局 | 顶部路由进度条；页面间淡入上移转场；导航项选中滑动下划线；**顶部书籍切换器 + 登录入口** |
| 登录 | 左品牌右表单分栏；登录 / 注册切换；提交 Toast 后进入首页 |
| 书架 | 书籍卡片 hover 上浮；封面渐变；状态点（已发布 / 整理中 / 规划中）；规划中置灰；**「＋ 导入语料」按钮** |
| 导入语料 | 步骤条；拖拽上传区；类型 / 模板选择；提交后走治理审核（Toast + 步骤点亮） |
| 首页 | 数字滚动（535/228/2）；语料库条；Hero 检索框聚焦放大；快捷入口卡片 hover 上浮 |
| 检索 | 筛选标签选中态；结果卡片 stagger 入场；"在图谱中展开"按钮 |
| 方剂详情 | 君臣佐使 chip 色标；栏目锚点平滑滚动；右侧 mini 图谱节点 hover |
| 案例/答题 | 答案区渐变遮罩；"揭晓"按钮触发擦除动画 |
| 评分报告 | 雷达图绘制动画；命中/遗漏/多余逐条高亮（绿/黄/红） |
| 图谱 | 节点 hover 放大 + 邻居高亮；力导"生长"入场；点击滑出详情抽屉 |
| 问答 | 打字机输出；**工具调用折叠卡**（查询→图谱→统计轨迹）；引用卡 hover 预览 |
| 收藏/练习 | 收藏成功图标弹跳；按钮点击涟漪 |

## 4. 示例数据

原型内置少量真实感示例数据（`assets/mock.js`）：
- **语料库**：5 部书（本书已发布 / 伤寒论整理中 / 金匮要略·温病条辨·神农本草经规划中）；
- 方剂「麻黄汤」「桂枝汤」「葛根汤」的组成/剂量/主治/条文；
- 案例（现病史/查体/辨证/治法/处方/效果）；
- 条文（《伤寒论》第 1 / 2 / 3 / 35 / 96 条）；
- 练习评分示例（命中/遗漏/多余）。

> 数据仅用于原型演示，正式系统从 PostgreSQL 真实数据读取。

## 5. 如何查看

1. 打开 `prototype/index.html`；
2. 顶部导航或页面内的卡片/链接即可跳转；
3. 部分页面（如图谱、问答）为静态示意，交互为前端模拟。

## 6. 与真实实现的差异

- 原型**无后端**，数据为内置示例；正式系统接 Spring Cloud + Agent。
- 原型不包含登录态校验、权限控制（正式系统由网关 JWT 实现）。
- 图谱为轻量 SVG/Canvas 示意；正式系统接 Neo4j 真实数据。
