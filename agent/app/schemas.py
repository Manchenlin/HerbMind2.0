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
    # 不设数字默认值，交给 retrieve() 读 RETRIEVAL_TOP_K，避免两处默认值打架导致配置失效
    top_k: int | None = Field(default=None, ge=1, le=10, description="检索条数（1~10），不传则取配置")
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
    tools_ms: int = Field(default=0, description="工具取证耗时（含所有轮次；0=没有调用工具）")


class ToolCallBrief(CamelModel):
    """一次工具调用的轨迹（同步问答回传 + 落库摘要同源）。

    `args` 只保留简短标量（字符串截断 40 字），避免把问题原文整段回传。
    """

    name: str = Field(description="工具名，如 search_formula")
    args: dict[str, Any] = Field(default_factory=dict, description="模型给工具的参数（已截断）")
    ok: bool = Field(description="工具是否执行成功；false=服务不可达或参数非法")
    hit: bool = Field(description="是否查到内容；false=查到了但库里没有")
    count: int = Field(default=0, description="命中条数")
    ms: int = Field(default=0, description="本次调用耗时（毫秒）")
    error: str = Field(default="", description="失败原因（仅 ok=false 时有值）")


class AskData(CamelModel):
    """POST /api/agent/ask/sync 的 data。"""

    answer: str = Field(description="回答正文（会带 [1][2] 这样的引用角标）")
    citations: list[Citation] = Field(default_factory=list, description="引用的资料列表")
    usage: AskUsage = Field(default_factory=AskUsage)
    degraded: bool = Field(
        default=False,
        description="true=大模型不可用或资料不足，answer 为降级内容（非模型生成）",
    )
    tool_calls: list[ToolCallBrief] = Field(
        default_factory=list,
        description="本次问答的工具调用轨迹（按执行顺序）；空数组=没有调用工具",
    )
    conversation_id: str = Field(
        default="",
        description="本次会话 ID；把它作为下一次请求的 conversationId 即可续接多轮",
    )


# ==================== 方剂加减查证（formula/diff） ====================


class FormulaDiffRequest(CamelModel):
    """POST /api/agent/formula/diff 的请求体。"""

    base_formula: str = Field(
        min_length=1, max_length=50,
        description="基础方：方名、别名或方剂 ID（如 桂枝汤 / f_5）",
    )
    add: list[str] = Field(
        default_factory=list, max_length=10,
        description="要加的药味名（如 ['葛根']）；不超过 10 味",
    )
    remove: list[str] = Field(
        default_factory=list, max_length=10,
        description="要减的药味名",
    )


class FormulaBrief(CamelModel):
    """方剂基本信息。efficacy / syndromeText / classicText 均为**语料原文摘录**，非系统推断。"""

    id: str
    name: str
    alias: str = ""
    herbs: list[str] = Field(default_factory=list, description="药味名（按库内顺序）")
    efficacy: str = Field(default="", description="功效——语料原文摘录")
    syndrome_text: str = Field(default="", description="证治归纳——语料原文摘录")
    page: str = ""
    classic_text: str = Field(default="", description="经典条文段落——语料原文摘录（不含条文号解析）")


class DiffMatchedFormula(CamelModel):
    """组成与结果**逐味完全一致**的成方。"""

    id: str
    name: str
    alias: str = ""
    efficacy: str = ""
    syndrome_text: str = ""
    page: str = ""
    classic_text: str = ""
    duplicate_name: bool = Field(
        default=False, description="true=库中该方名有重复收录（同方多条目），不是两个不同的方"
    )


class DiffSimilarFormula(CamelModel):
    """组成相近但**并非同一方**，仅供对照。"""

    id: str
    name: str
    jaccard: float = Field(description="药味集合 Jaccard 相似度（0~1）")
    note: str = Field(default="", description="固定提示：非同一方，仅供参考")


class FormulaDiffData(CamelModel):
    """POST /api/agent/formula/diff 的 data。"""

    base: FormulaBrief
    removed: list[str] = Field(default_factory=list, description="实际从基础方去掉的药味")
    added: list[str] = Field(default_factory=list, description="实际新增的药味")
    result_herbs: list[str] = Field(default_factory=list, description="加减后的结果组成")
    matched_formulas: list[DiffMatchedFormula] = Field(
        default_factory=list, description="组成完全一致的成方；空数组表示库内无对应记载"
    )
    match_hint: str = Field(default="", description="未命中时的说明（是结论，不是报错）")
    similar_formulas: list[DiffSimilarFormula] = Field(default_factory=list)
    warnings: list[str] = Field(
        default_factory=list, description="药名疑似解析残留、要减的药不在方中等提示"
    )
    dose_compared: bool = Field(
        default=False, description="本次是否比对了剂量（当前库内剂量缺失，恒为 false）"
    )
    notice: str = Field(default="", description="免责声明：不推断功效、不构成处方建议")


# ==================== 会话历史（history） ====================


class ConversationBrief(CamelModel):
    """会话列表里的一条。"""

    id: str = Field(description="会话 ID，可直接作为下一次 ask 的 conversationId")
    title: str = Field(default="", description="标题（取首个问题的前 30 字）")
    created_at: str = Field(default="", description="创建时间（ISO 8601，带时区）")
    message_count: int = Field(default=0, description="消息条数（只算 user/assistant）")
    last_at: str = Field(default="", description="最后一条消息时间；空串=还没有消息")


class HistoryData(CamelModel):
    """GET /api/agent/history 的 data。"""

    conversations: list[ConversationBrief] = Field(
        default_factory=list, description="按创建时间倒序；空数组=还没有会话"
    )
    total: int = Field(default=0, description="本次返回的条数（不是全库总数）")
