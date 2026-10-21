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

    # ---------- 数据源 ----------
    pg_dsn: str = "postgresql://postgres:postgres@localhost:5432/herbmind"
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "herbmind123"
    redis_url: str = "redis://localhost:6379/0"

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
