"""对外数据模型：与后端 Java 侧保持同一套响应外壳。

约定（见 project_plan/09_API契约清单.md §12）：
    { "code": 0, "msg": "success", "data": ... }
    code=0 成功，非 0 失败；JSON 字段一律 camelCase。
"""

from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

T = TypeVar("T")


class CamelModel(BaseModel):
    """基类：Python 用 snake_case，出参自动转 camelCase。"""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class R(CamelModel, Generic[T]):
    """统一响应外壳 R<T>。"""

    code: int = Field(default=0, description="0=成功")
    msg: str = Field(default="success", description="提示信息")
    data: T | None = Field(default=None, description="业务数据")

    @classmethod
    def ok(cls, data: T | None = None, msg: str = "success") -> "R[T]":
        return cls(code=0, msg=msg, data=data)

    @classmethod
    def fail(cls, code: int, msg: str) -> "R[T]":
        return cls(code=code, msg=msg, data=None)


class DepStatus(CamelModel):
    """单个外部依赖的探测结果。"""

    ok: bool = Field(description="是否可用")
    detail: str = Field(default="", description="成功时给规模信息，失败时给原因")
    latency_ms: int = Field(default=0, description="探测耗时（毫秒）")


class HealthData(CamelModel):
    """GET /api/agent/health 的 data。"""

    status: str = Field(description="ok=全部依赖正常；degraded=有依赖不通但服务本身活着")
    service: str
    version: str
    llm: dict[str, Any] = Field(description="模型名 + key 是否已配置（不调用、不花钱）")
    deps: dict[str, DepStatus] = Field(description="postgres / neo4j / redis 探测结果")
    pg_pool: dict[str, Any] = Field(
        default_factory=dict,
        description="PG 连接池统计：poolSize=池内连接数，poolAvailable=空闲数，requestsWaiting=排队数",
    )


# ==================== 问答（ask/sync） ====================


class AskRequest(CamelModel):
    """POST /api/agent/ask/sync 的请求体。"""

    question: str = Field(min_length=2, max_length=500, description="用户问题")
    top_k: int = Field(default=5, ge=1, le=10, description="检索条数（1~10）")
    ref_type: Literal["formula", "case"] | None = Field(
        default=None,
        description="限定资料类型：formula=方剂、case=医案；不传=全部（注意：条文暂无向量）",
    )
    conversation_id: str | None = Field(
        default=None,
        description="续接会话 ID（M2 会话记忆落地后生效，当前仅透传）",
    )


class Citation(CamelModel):
    """一条引用：前端拿它渲染"引用卡"，点开能跳原文。"""

    id: str = Field(description="内容单元 ID，如 cu_9")
    ref_type: str = Field(description="来源类型 formula / case")
    ref_id: str = Field(description="来源实体 ID，如 f_3")
    title: str = Field(default="", description="标题（方名 / 医案名）")
    snippet: str = Field(description="原文片段，用于前端预览")
    score: float = Field(description="余弦相似度（0~1，越大越像）")


class AskUsage(CamelModel):
    """耗时与 token 用量，便于观察成本与性能。"""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    retrieve_ms: int = Field(default=0, description="向量检索耗时（含 embedding 调用）")
    llm_ms: int = Field(default=0, description="大模型生成耗时")


class AskData(CamelModel):
    """POST /api/agent/ask/sync 的 data。"""

    answer: str = Field(description="回答正文（会带 [1][2] 这样的引用角标）")
    citations: list[Citation] = Field(default_factory=list, description="引用的资料列表")
    usage: AskUsage = Field(default_factory=AskUsage)
    degraded: bool = Field(
        default=False,
        description="true=大模型不可用或资料不足，answer 为降级内容（非模型生成）",
    )
