"""配置：全部从环境变量 / .env 读取（pydantic-settings）。

约定：
- 字段名与 .env 变量名大小写无关（llm_api_key <-> LLM_API_KEY）
- 不在代码里写死任何密钥（.env 已被 .gitignore 挡住）
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Agent 服务配置。新增变量时同步补 .env.example。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---------- 服务 ----------
    app_name: str = "herbmind-agent"
    app_version: str = "0.1.0"
    app_port: int = 8091

    # ---------- 大模型（OpenAI 兼容协议，默认硅基流动） ----------
    llm_api_base: str = "https://api.siliconflow.cn/v1"
    llm_api_key: str = ""
    llm_model: str = "Qwen/Qwen2.5-7B-Instruct"

    # ---------- 向量模型（必须与库内 1024 维向量同源） ----------
    embedding_model: str = "BAAI/bge-m3"
    embedding_dim: int = 1024

    # ---------- 检索 / 问答 ----------
    retrieval_top_k: int = 5          # 每次召回几条内容单元（5 条约 3400 字，别太多稀释重点）
    # 相似度下限：2026-10-22 实测——相关问题 0.61~0.73，无关问题（问天气）0.42~0.44，
    # 所以 0.5 是干净的分界线：低于它直接判"无命中"，连 LLM 都不用调（省时省钱）
    retrieval_min_score: float = 0.5
    llm_max_tokens: int = 800          # 回答长度上限
    llm_temperature: float = 0.2       # 医学问答求稳，不要发挥

    # ---------- 数据源（账号密码一律只从 .env 读，源码里不留真实凭据） ----------
    pg_dsn: str = "postgresql://postgres@localhost:5432/herbmind"
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""
    redis_url: str = "redis://localhost:6379/0"

    # ---------- 各 svc 的 /internal 接口（工具的数据源） ----------
    # 工具不再直连 PG/Neo4j，统一走 svc 的 /internal，保证与 BFF 同一份检索口径。
    # docker 部署时改成 compose 里的服务名（http://svc-search:8083 等）。
    svc_catalog_url: str = "http://localhost:8082"
    svc_search_url: str = "http://localhost:8083"
    svc_graph_url: str = "http://localhost:8085"
    svc_connect_timeout: float = 1.0    # 连不上就快速失败，别让问答卡在握手
    svc_read_timeout: float = 5.0       # 单次 /internal 调用的读超时

    # ---------- Agent 工具调用循环 ----------
    # 出问题时的总开关：false → 完全退回单轮 RAG（行为与本轮改造前一致）
    agent_tools_enabled: bool = True
    agent_max_tool_rounds: int = 3      # 最多几轮工具取证；轮次越多越容易跑偏
    agent_tool_budget_ms: int = 15000   # 一次问答里工具阶段的累计预算，超了就停止取证直接生成
    agent_tool_timeout: float = 5.0     # 单个工具的硬超时（失败重试 1 次）
    # 清单类问题（"哪些方剂含有麻黄"）强制首轮取证：实测 Qwen2.5-7B 在强"只用资料"的
    # system 下会拿三五条片段凑答案，必须用 tool_choice=required 顶一下。普通问答不受影响。
    agent_force_tools: bool = True

    # ---------- 会话历史 ----------
    history_limit: int = 20             # GET /api/agent/history 默认条数（上限 50）
    memory_messages: int = 6            # 多轮记忆：带 conversationId 时回填的历史消息条数

    # ---------- 跨域 ----------
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        """把逗号分隔的 CORS_ORIGINS 拆成列表。"""
        return [x.strip() for x in self.cors_origins.split(",") if x.strip()]

    @property
    def llm_configured(self) -> bool:
        """key 是否已配置（health 只报状态，不校验额度）。"""
        return bool(self.llm_api_key.strip())


@lru_cache
def get_settings() -> Settings:
    """单例配置（lru_cache 避免重复读 .env）。"""
    return Settings()
