# A 域 · 实机验收结果

- 时间：2026-10-27 19:20（Asia/Shanghai）
- 环境：Windows 11 / Docker 29.9.2（pgvector/pgvector:pg17）/ Java 25.0.2 / Node 22.17.0
- 数据：herbmind_data.sql → formula=245 · case=290 · quote=568 · unit=535（向量 535）
- 服务：svc-catalog:8082 · svc-search:8083 · svc-insight:8086 · bff:8090 · gateway:8080 · Vite:5173
- 结果：**38 / 38 通过**

```
== A1 catalog ==
  [OK]   书架 books
  [OK]   统计 245 方
  [OK]   统计 535 向量
  [OK]   目录树 bk_1
  [OK]   节点详情 formulas
  [OK]   节点详情 breadcrumb
  [OK]   方剂 f_1 麻黄汤
  [OK]   方剂 herbs 字段
  [OK]   方剂 quotes 字段
  [OK]   医案 cs_1 sections
  [OK]   医案 cs_1 siblings
  [OK]   条文 q_1 items
  [OK]   条文列表 /quote/list
  [OK]   今日方证 daily
== A2 search ==
  [OK]   检索 麻黄汤
  [OK]   检索 自然语言
  [OK]   检索 分面 types
  [OK]   条文反向索引
  [OK]   条文索引覆盖 568
  [OK]   语义检索 POST
  [OK]   供 Agent 的 recall
== insight ==
  [OK]   用药频次
  [OK]   证候分布
  [OK]   章节分布
  [OK]   CSV 导出
  [OK]   研究包
== A4 BFF ==
  [OK]   首页 stats
  [OK]   首页 today
  [OK]   首页 hotHits(search)
  [OK]   首页 graph
  [OK]   BFF 目录树
  [OK]   BFF 节点详情
  [OK]   BFF 方剂页
  [OK]   BFF 医案页
  [OK]   BFF 条文页
  [OK]   BFF 条文列表
  [OK]   BFF 检索
  [OK]   BFF 导出

全部通过：38 项
```

