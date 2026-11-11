# 🧪 单元测试报告

## 项目信息

- **项目名称**: HerbMind 本草心智
- **测试框架**: vitest 2.1.8（TypeScript） + pytest 9.1.1（Python 3.11.17 / conda `herbmind`）
- **运行时间**: 2026-11-11 15:05
- **总耗时**: 约 1.85s（vitest 1.28s + pytest 0.57s）
- **测试位置**: 仓库根 `test/`（不改动 `agent/tests` 既有 198 例，也不改任何源码）

## 概览

| 指标 | 数值 |
|------|------|
| 检测单元数 | 15 |
| 生成测试数 | 84 |
| ✅ 通过 | 84 |
| ❌ 失败 | 0 |
| ⏭️ 跳过 | 0 |
| 📊 通过率 | 100% |

## 复跑方式

```bash
# 前端（vitest，从 frontend/ 跑，依赖从 frontend/node_modules 解析）
cd frontend && npx vitest run --config ../test/vitest.config.mts

# 后端 Agent（pytest，conftest.py 已把 agent/ 插进 sys.path）
cd test && python -m pytest . -q
```

## 各单元测试结果

### P1 - 重要功能模块

| 单元 | 文件 | 测试数 | 通过 | 失败 | 状态 |
|------|------|--------|------|------|------|
| layoutNeighbors | frontend/src/utils/graphLayout.ts | 8 | 8 | 0 | ✅ |
| layoutFormula | frontend/src/utils/graphLayout.ts | 3 | 3 | 0 | ✅ |
| layoutMap | frontend/src/utils/graphLayout.ts | 3 | 3 | 0 | ✅ |
| mapGroups | frontend/src/utils/graphLayout.ts | 5 | 5 | 0 | ✅ |
| isEntityMissing | frontend/src/api/graph.ts | 4 | 4 | 0 | ✅ |
| graphErrMsg | frontend/src/api/graph.ts | 8 | 8 | 0 | ✅ |

### P2 - 工具函数

| 单元 | 文件 | 测试数 | 通过 | 失败 | 状态 |
|------|------|--------|------|------|------|
| nodeRadius | frontend/src/utils/graphLayout.ts | 1 | 1 | 0 | ✅ |
| ok_result / miss_result / error_result | agent/app/tools/common.py | 7 | 7 | 0 | ✅ |
| resolve_label | agent/app/tools/graph.py | 19 | 19 | 0 | ✅ |
| _rel_types | agent/app/tools/graph.py | 6 | 6 | 0 | ✅ |
| _segments | agent/app/tools/score.py | 4 | 4 | 0 | ✅ |
| _bigrams | agent/app/tools/score.py | 3 | 3 | 0 | ✅ |
| _match_items | agent/app/tools/score.py | 6 | 6 | 0 | ✅ |
| _norm | agent/app/tools/score.py | 2 | 2 | 0 | ✅ |
| _score_of | agent/app/tools/score.py | 5 | 5 | 0 | ✅ |

## 为什么测这些

| 被测点 | 它守住的红线 / 契约 |
|--------|---------------------|
| `layoutFormula` 不给相关方造边 | 「组成相近」不是库里的关系，画出边等于凭空造关系（设计红线一） |
| `layoutMap` 坐标只做线性映射 | 后端承诺「同 version 同一张图」，前端重排会让截图与讲解失效 |
| `mapGroups` 最多 8 组上色、其余灰 | 图例里每种颜色都必须真实对应图上的一组，不能让读者误读分组 |
| `isEntityMissing` / `graphErrMsg` | 4000 / 4040 / 5000 三种错误必须给出不同提示，前端唯一的分流点 |
| `_match_items` 不做包含匹配 | 「脉浮」不能算命中「脉浮缓」，否则分数虚高 |
| `_segments` 不在条目内拆词 | 模型切条会把「脉浮缓」拆成「脉浮」+「脉缓」（实核过），所以切条归代码 |
| `ok_result` / `miss_result` / `error_result` | `ok=False`（没查成）与 `hit=False`（查了没有）语义不同，契约 §13.3 |
| `resolve_label` | 标签白名单在本地拦截，不把「模型传错参数」混成「图谱服务坏了」 |

## 失败详情

无。

## 未覆盖区域（如实列出）

1. `backend/herbmind-bff`：**没有 `src/test` 目录**，`GraphExceptionAdvice` 的状态码映射（400→4000 / 404→4040 / 503→5030）零覆盖。这是本轮新增代码里唯一没有自动化保护的 P0 逻辑。
2. `backend/herbmind-gateway`：JWT 白名单与 401 `R` 外壳无测试（全项目仅 `svc-graph` 有测试）。
3. `frontend/src/views/*.vue`：无组件级测试（需引入 `@vue/test-utils` + `jsdom`，本轮未引入依赖）。
4. `frontend/src/api/request.ts`：拦截器需 mock adapter 才能测，本轮只间接覆盖（通过 `graph.ts` 的封装形状）。

## 改进建议

1. **给 `GraphExceptionAdvice` 补 JUnit 测试**：这是唯一决定「前端能不能区分 4040 与 5000」的地方，且纯逻辑、易测（构造 `FeignException` 用 `FeignException.errorStatus`）。
2. **把 `test/` 纳入统一入口**：`CODEBUDDY.md` §八 目前没有前端测试命令，建议补一行 `cd frontend && npx vitest run --config ../test/vitest.config.mts`。
3. **vitest 以 `--no-save` 装进了 `frontend/node_modules`**：要长期保留测试，需在 `frontend/package.json` 的 `devDependencies` 里显式加 `vitest`，否则别人 `npm ci` 后跑不了。是否加取决于前端负责人（属域2 模块）。
4. 组件级测试优先级最高的三个页面：`GraphView`（实体兜底重试）、`GraphMapView`（图例与配色一致）、`GraphFormulaView`（null 字段兜底）。
