# 11 · LangChain 1.x 学习实践指南

> 本项目**刻意设计成 LangChain 1.x 的实践场**：每个模块都对应一项 LangChain 1.x 能力。
> 环境：conda env `herbmind`（Python 3.11）；模型走硅基流动（OpenAI 兼容），**无需本地 GPU**。

## 1. 为什么要借这个项目学

- 有**真实知识底座**（535 条方证 + 向量 + 图谱），不是玩具数据。
- 有**真实需求**（问答/评分/推演），每学一项能力都有落地处。
- 现有系统的 RAG 是 `httpx` 直调，**正是"从裸调用升级到 LangChain 1.x"的最佳练手点**。

## 2. 能力矩阵（LangChain 1.x ↔ 项目落点）

| 能力 | 学什么 | 项目落点 | 难度 |
|---|---|---|---|
| LCEL / Runnable | `prompt \| llm \| parser` | RAG 基础链 | ★ |
| Chat 模型接入 | `ChatOpenAI(base_url=…)` | 硅基流动云 | ★ |
| Embeddings | `OpenAIEmbeddings(bge-m3)` | 向量化/检索 | ★ |
| Retriever | `PGVector` 检索器 | 语义召回 | ★★ |
| TextSplitter | 知识块切分 | content_unit 构建 | ★★ |
| **Tools（`@tool`）** | 函数即工具 | 11 个业务工具 | ★★ |
| **Agent（`create_agent`）** | 中间件式 Agent | 智能问答中枢 | ★★★ |
| LangGraph 状态机 | 自定义 `state_schema`、条件边 | 多轮取证 | ★★★ |
| Memory | checkpointer / 长期记忆 | 会话与画像 | ★★ |
| **结构化输出** | `with_structured_output` | 辨证评分 | ★★ |
| Middleware | 人类在环/摘要/重试 | 练习确认 | ★★★ |
| Streaming | `astream_events` + SSE | 打字机/工具轨迹 | ★★ |
| Tracing | LangSmith/LangFuse | 质量回归 | ★★ |
| Evaluation | 评测集 | RAG 回归 | ★★★ |

## 3. 梯度练习任务（L1 → L8）

### L1 · 单轮 RAG 链（对齐现有问答）
```python
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
chain = ChatPromptTemplate.from_template("依据以下资料回答：{ctx}\n问：{q}") | model | StrOutputParser()
```
**验收**：对"桂枝汤主治"给出与现有系统一致的答案。

### L2 · 加一个工具（体验 function calling）
```python
@tool
def search_formula(name: str) -> str:
    """按方名查询方剂信息"""
    return catalog_client.get_by_name(name)
```
**验收**：模型能自主决定调用它。

### L3 · 换 `create_agent`，接全部 11 工具
**验收**：多跳问题（"无汗而喘、项背强几几，用麻黄汤怎么加减"）能串起 `search_formula → graph_neighbors → formula_diff`。

### L4 · 接 checkpointer，多轮上下文
**验收**：追问"那如果又见烦躁呢"能接着上文。

### L5 · 结构化输出：辨证评分
```python
class SyndromeScore(BaseModel): hit: list[str]; miss: list[str]; extra: list[str]; score: int
```
**验收**：对用户答案输出稳定 JSON，直接入库 `answer_score`。

### L6 · Middleware：人类在环 + 摘要
**验收**：提交练习前弹确认；超长会话自动摘要不丢上下文。

### L7 · 多 Agent 分工（Supervisor）
`assistant`（问答）/ `coach`（辨证教练）/ `research`（科研）三专家 + 路由。
**验收**：不同意图路由到不同子 Agent。

### L8 · 评测集 + Tracing 回归
构造（问题 → 期望引用）评测集，用 LangSmith 跑回归。
**验收**：改动检索参数后，能量化精度变化。

## 4. 环境准备

```bash
# 已有 conda 环境（Python 3.11）
conda activate herbmind
pip install -r agent/requirements.txt
# 关键依赖：langchain>=1.0 langchain-core>=1.0 langchain-openai langchain-postgres langgraph neo4j fastapi uvicorn
```

`.env` 关键变量：
```
LLM_API_BASE=https://api.siliconflow.cn/v1
LLM_API_KEY=sk-...
LLM_MODEL=Qwen/Qwen2.5-7B-Instruct
EMBEDDING_MODEL=BAAI/bge-m3
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=...
```

> 说明：生成与 Embedding 都走云端，**无需下载 2.3GB 本地权重**；代码预留 `local` 回退开关，待 GPU 到位再切。

## 5. 学习产出物建议

| 产出 | 说明 |
|---|---|
| `agent/README.md` | 记录每个 L 任务的实现要点与踩坑 |
| 评测集 `evals/` | 问题→期望引用，做回归 |
| 学习笔记 | 每掌握一项能力，写一段"能力→代码→现象"记录 |
| 图谱调试图 | Agent 工具调用轨迹截图，直观展示多跳 |

## 6. 与毕业/论文结合

本项目可支撑：RAG 检索质量对比（混合召回 vs 纯向量）、Agent 工具编排效果、方证知识图谱的构建与挖掘、练习评分算法的有效性。→ 均有**可量化指标**与**可复现数据**。
