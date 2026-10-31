# 08 · Agent 服务设计（LangChain 1.x）

> 服务名：`herbmind-agent`（Python 3.11 / conda env `herbmind`），FastAPI + **LangChain 1.x**（构建在 LangGraph 之上），端口 :8091，注册 Nacos，经网关路由 `/api/agent/**`。
> 定位：**平台智能中枢**——问答、辨证教练、加减查证、评分、个性化推荐都经它调度。
> ⚠️ 本服务所有输出受 **00 文档「设计红线」** 约束：只查证与引用，不推断疗效、不给处方建议。

## 1. 为什么是 LangChain 1.x（而非旧版/裸调用）

现有系统的 RAG 是 `httpx` 直调 LLM，**没有用 LangChain**。1.x 的价值在于：

| 能力 | 用在哪 |
|---|---|
| `create_agent`（中间件式 Agent） | 多工具调度（查方/图谱/统计/评分…） |
| LangGraph 状态机 | 多轮取证、条件边、循环 |
| `@tool` | 把后端能力封装成工具 |
| `state_schema` / checkpointer | 会话记忆、上下文压缩 |
| `with_structured_output` | 辨证评分、推荐列表等结构化输出 |
| middleware | 人类在环、摘要、工具重试、引用校验 |
| `astream_events` | SSE 流式、前端打字机、工具轨迹可视化 |
| Tracing（LangSmith/LangFuse） | 观测每次工具调用，做质量回归 |

> 详细梯度练习见 [11 · LangChain 1.x 学习实践指南](11_LangChain1.x学习实践指南.md)。

## 2. 关键 API（1.x 范式）

```python
from langchain.agents import create_agent
from langchain.agents.middleware import (
    SummarizationMiddleware, HumanInTheLoopMiddleware, ToolRetryMiddleware,
)
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from typing import TypedDict
from langchain_core.messages import AnyMessage

# 1) 模型（兼容 OpenAI 协议，指向硅基流动）
model = ChatOpenAI(
    model="Qwen/Qwen2.5-7B-Instruct",
    base_url="https://api.siliconflow.cn/v1",
    api_key=os.environ["LLM_API_KEY"],
    temperature=0.2,
)

# 2) 自定义状态（在 MessagesState 基础上扩展）
class HerbMindState(TypedDict):
    messages: list[AnyMessage]
    user_id: str
    filters: dict          # 经典/章节过滤
    citations: list[dict]  # 引用（经典名+页码+chunk_id）
    step: int

# 3) 创建 Agent（中间件式，返回可流式的编译图）
agent = create_agent(
    model=model,
    tools=[search_formula, search_case, semantic_recall,          # 一期 6 个高频
           graph_neighbors, syndrome_score, dosage_convert],
    # 二期再挂：search_quote / graph_path / herb_statistics / formula_diff / get_user_profile
    system_prompt=SYSTEM_PROMPT,          # 经方助手人设 + 必须给引用
    state_schema=HerbMindState,
    middleware=[
        SummarizationMiddleware(max_tokens=3000),   # 长对话压缩
        ToolRetryMiddleware(max_retries=2),         # 工具失败重试
        HumanInTheLoopMiddleware(interrupt_on={"submit_training": True}),  # 提交前人工确认
    ],
    checkpointer=InMemorySaver(),         # 生产可换 AsyncPostgresSaver
)
```

## 3. 服务结构

```
agent/
├── app/
│   ├── main.py            # FastAPI 入口，:8091
│   ├── config.py          # 环境变量/模型/向量库配置
│   ├── llm.py             # ChatOpenAI / Embeddings 工厂
│   ├── agents/
│   │   ├── assistant.py   # 主问答 Agent（create_agent）
│   │   ├── coach.py       # 辨证教练（多轮追问）
│   │   └── supervisor.py  # 多 Agent 分工（问答/教练/科研）——L7
│   ├── tools/
│   │   ├── catalog.py     # search_formula/case/quote
│   │   ├── recall.py      # semantic_recall
│   │   ├── graph.py       # graph_neighbors/graph_path
│   │   ├── stats.py       # herb_statistics
│   │   ├── dosage.py      # dosage_convert
│   │   ├── formula.py     # formula_diff
│   │   └── score.py       # syndrome_score
│   ├── rag/
│   │   ├── retriever.py   # pgvector + pg_jieba 混合召回
│   │   ├── rerank.py      # bge-reranker（可选）
│   │   └── context.py     # 上下文拼装 + 引用抽取
│   ├── memory/store.py    # 长期记忆（用户方证库/偏好，写 PG）
│   ├── clients/           # 调 Java 服务的 HTTP 客户端
│   ├── prompts/           # 提示词（版本化：system / coach / grade）
│   ├── observability.py   # Tracing（LangSmith / LangFuse）配置
│   └── schemas.py         # Pydantic：评分/推荐/引用
├── evals/                 # 评测集（问题 → 期望引用），做回归
├── requirements.txt
└── .env.example
```

## 4. 工具（Tools）设计

| 工具（`@tool`） | 期 | 入参 | 返回 | 依赖 |
|---|---|---|---|---|
| `search_formula` | **一期** | name / herb / syndrome | 方剂列表 | svc-search `/internal/search?type=formula`（原写 svc-catalog，2026-10-31 更正） |
| `search_case` | **一期** | diagnosis / formula / symptom | 案例列表 | svc-search `/internal/search?type=case`（原写 svc-catalog，2026-10-31 更正） |
| `semantic_recall` | **一期** | query, top_k | chunk + score | svc-search `/internal/search/recall` |
| `graph_neighbors` | **一期** | entity, label, hops | 邻居子图 | svc-graph `/internal/graph/neighbors` |
| `syndrome_score` | **一期** | user_syndrome, ref_syndrome | 命中/遗漏/多余 + 分 | LLM + 证候字典 |
| `dosage_convert` | **一期** | value, unit, dynasty | 现代克数 + 依据 | PG dosage_rule |
| `search_quote` | 二期 | article_no / classic / keyword | 条文列表 | svc-catalog |
| `graph_path` | 二期 | from, to | 路径列表 | svc-graph |
| `herb_statistics` | 二期 | scope(经典/章节), metric | 频次表 | svc-insight |
| `formula_diff` | 二期 | base_formula, add[], remove[] | 结果组成 + **命中的经典成方（含原文条文与出处）** + 相似成方（Jaccard，标注"非同一方"）；**不返回任何功效推断** | PG `formula_herb`（当前）/ svc-catalog（就绪后迁移） |
| `get_user_profile` | 二期 | user_id | 画像/薄弱点 | svc-training |

> **一期只挂 6 个高频工具**（`search_formula`、`search_case`、`semantic_recall`、`graph_neighbors`、`syndrome_score`、`dosage_convert`）——工具数 ≤ 6~8 可显著提升 LLM 选择准确率；二期再补至 11。

```python
from langchain_core.tools import tool

@tool
def graph_neighbors(entity: str, label: str, hops: int = 1) -> dict:
    """查询知识图谱中某实体的邻居子图。entity=实体名, label=节点类型, hops=跳数。"""
    return graph_client.neighbors(entity, label, hops)
```

## 5. RAG 管线

```
用户问题
  → 意图识别（结构化查询 / 语义检索 / 图谱多跳 / 闲聊）
  → 混合召回：
        pgvector 余弦 Top-K  ⊕  pg_jieba 全文 Top-K  ⊕  Neo4j 邻居扩展
  → 元数据过滤（经典 / 章节 / chunk_type）+ 可选 Reranker(bge-reranker)
  → Agent 决定调用工具、多轮取证（ReAct 风格）
  → 生成答案 + citations(经典名 + 页码 + chunk_id)
  → SSE 流式推前端（打字机 + 工具轨迹 + 引用卡）
```

知识块沿用 `content_unit`（原 `rag_chunk` 升级；1 方证单元 = 1 chunk），`unit_type` 细化来源，便于按类型过滤与加权重排。

## 6. 记忆（Memory）

| 类型 | 实现 | 用途 |
|---|---|---|
| 短期 | ~~checkpointer（`thread_id` = 会话 ID）~~ → **`agent_message` 表**（取最近 6 条） | 多轮对话上下文 |
| 压缩 | `SummarizationMiddleware`（**未实现**） | 超长会话自动摘要 |
| 长期 | 写 PG（`learning_profile` / `user_*`，**未实现**） | 用户偏好、我的方证库、薄弱点 → 个性化 |

> ⚠️ **有意偏差（2026-10-31，域3 提出，待三人 review）**：短期记忆**不用** LangGraph checkpointer，
> 直接读 `agent_message` 表里最近 6 条 user/assistant 消息。
>
> 理由：这张表本来就要为 `GET /api/agent/history` 落库（见 09 §13.4），同一份数据两用；
> 引入 checkpointer 会多一个依赖 + 一套 schema（生产要 Postgres/SQLite saver、测试还要造假实现），收益不抵成本。
>
> 实现口径：历史消息插在 system 之后、当前问题之前；system 里额外声明
> 「历史对话只用于理解上下文，不是【资料】，不得引用其中的编号」——否则模型会引用自己上一轮的回答。

## 7. 结构化输出（评分/推荐）

```python
from pydantic import BaseModel, Field

class SyndromeScore(BaseModel):
    hit: list[str] = Field(description="命中的证候关键词")
    miss: list[str] = Field(description="遗漏的证候关键词")
    extra: list[str] = Field(description="多出的、原著没有的")
    score: int = Field(ge=0, le=100, description="证候得分")

scorer = model.with_structured_output(SyndromeScore)
result = scorer.invoke([...])   # -> SyndromeScore
```

用于：辨证评分（M3）、方剂推荐列表、条文白话释义、学习路径生成。

## 8. 流式与可观测

- **流式**：`async for ev in agent.astream_events(inputs, config, version="v2")` → 过滤 `on_chat_model_stream`（逐字）、`on_tool_start/end`（工具轨迹）→ 以 SSE（`text/event-stream`）推给前端。
- **Tracing**：设置 `LANGSMITH_TRACING=true` / LangFuse 环境变量，记录每次工具调用入参、耗时、结果摘要，落 `agent_tool_call` 表，供前端"工具轨迹"回放与质量分析。

## 9. 对外 API

| 端点 | 方法 | 说明 |
|---|---|---|
| `/api/agent/ask` | POST | 主问答（SSE 流式） |
| `/api/agent/ask/sync` | POST | 同步问答（调试/降级） |
| `/api/agent/coach` | POST | 辨证教练多轮追问 |
| `/api/agent/formula/diff` | POST | 方剂加减**查证**（只比对组成 + 引用原文，不推断功效） |
| `/api/agent/grade` | POST | 练习自动评分（结构化） |
| `/api/agent/health` | GET | 健康检查（白名单） |

> 网关路由：`/api/agent/ask*` 与 `/api/agent/health`；`ask/sync` 供调试。

## 10. 依赖（requirements 摘要）

```
fastapi
uvicorn[standard]
pydantic
pydantic-settings
langchain>=1.0
langchain-core>=1.0
langchain-openai
langchain-postgres
langgraph
neo4j
psycopg[binary]
httpx
python-dotenv
```

## 11. 与 Java 服务协作

Agent 不直接连业务库做写操作，而是：
- **读**：经 `clients/` 调 svc-catalog / svc-search / svc-graph / svc-insight 的 `/internal/**`（服务间直连，带 `X-User-Id`）。
- **写**（评分、会话留痕）：写自己的 `agent_*` 表；**评分结果不由 Agent 落库**——由 BFF 编排：`POST /api/biz/train/answer` → BFF 调 svc-training 存答案 → 调 Agent `/api/agent/grade` → 调 `svc-training /internal/training/score` 落分。
- 网关负责对外的 JWT 鉴权；Agent 信任网关透传的用户头。

> ✅ **2026-10-31 落地情况**（域3 提出，待三人 review）：
>
> 1. `clients/` 已建（`agent/app/clients/{base,catalog,search,graph}.py`）：`httpx.AsyncClient` 单例、
>    connect 1s / read 5s 超时、连接池 20；成功响应按**裸 DTO** 解析，非 2xx 取 `R.msg` 抛 `SvcError`，
>    连不上/超时统一 `SvcError(status=0)`。工具层据此区分「查不到（4040 → hit=false）」与「服务坏了（ok=false）」。
> 2. 一期 4 个工具**全部**改走 `/internal`；`syndrome_score` / `dosage_convert` 仍未挂（依赖的表 0 行）。
> 3. **`ask` 主链的向量检索仍直连 pgvector**（`app/rag/retriever.py` 未迁）：它的 0.5 阈值 + 方剂 6:4 配额
>    是按真实问答质量校准出来的，本期只迁工具，避免同时改两处导致问答质量不可归因。
> 4. 工具调用循环手写（`app/agent/runner.py`，`bind_tools` + `tool_calls` 判空），**不用** `create_agent`：
>    需要精确控制 SSE 事件时序、轮次上限（默认 3）、工具阶段预算（默认 15s）、失败降级。
>    `AGENT_TOOLS_ENABLED=false` 可一键回退到单轮 RAG。
> 5. **清单类问题强制取证**（`needs_tool_evidence` + `AGENT_FORCE_TOOLS`）：
>    实测 Qwen2.5-7B 在「只能依据【资料】回答」的强 system 下，面对「哪些方剂含有麻黄」会拿
>    召回到的 3~5 条片段凑一份"完整清单"，一次工具都不调；提示词里连写三版"必须先调工具"均无效
>    （`run_tool_loop` 的 `used` 恒为 False），只有 `tool_choice="required"` 能稳定触发。
>    因此对**列举/统计/核对清单**这类问法（正则刻意写窄，见 `_NEEDS_EVIDENCE`）首轮强制取证，
>    第二轮回到 `auto`；普通问答（解释条文、归纳证治）不强制，不受影响。绑定失败自动降级为 `auto`。

## 12. LLM 健壮性与成本

| 项 | 约定 |
|---|---|
| 超时 | 单次 LLM 调用 30s；整体问答 60s |
| 重试 | 工具失败重试 2 次（`ToolRetryMiddleware`）；LLM 失败降级 `degraded=true` |
| 熔断 | 云端连续失败 → 熔断 30s，返回"稍后再试" |
| 成本 | 单次问答 token 上限；每用户每日配额 |
| 采样 | 评分类 `temperature=0`；生成类 ≤ 0.3 |
| 兜底 | 药味 / 剂量比对用**规则**（集合运算），仅"证候语义比对"交 LLM |
