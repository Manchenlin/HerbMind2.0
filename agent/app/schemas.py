"""对外数据模型：与后端 Java 侧保持同一套响应外壳。

约定（见 project_plan/09_API契约清单.md §12）：
    { "code": 0, "msg": "success", "data": ... }
    code=0 成功，非 0 失败；JSON 字段一律 camelCase。
"""

from typing import Any, Generic, TypeVar

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
