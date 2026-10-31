import request from './request'

/**
 * 域3 图谱接口（`/api/biz/graph/**`，字段口径见 09 契约 §15，已冻结）。
 *
 * 链路：前端 → 网关 :8080 → BFF(`bff/graph`) → svc-graph `/internal/graph/**`。
 * **BFF 那层由域2 按 §15.6 步骤 2 实现**，在那之前调用会拿到 404 —— 本文件**不提供假数据、
 * 也不 mock 降级**：拿不到就照实报错，免得页面看起来"能用"其实在空转。
 *
 * 注意几个与旧示意数据（`mock/domain3.ts`）不同的硬约束：
 *   · 节点只有 Formula / Herb 两类，**没有 Syndrome / Symptom**；
 *   · 边只有 `COMPOSED_OF` 一类（方 → 药），**没有 MODIFIES / SIMILAR_TO**；
 *   · 节点 id 是稳定业务 ID（方剂 `f_1`、药味 `h_麻黄`），不是 Neo4j elementId；
 *   · 剂量 `dose` 是**字符串**（后端为避免浮点误差统一转字符串，如 "3"），没有就是 null。
 */

/** 节点类型：只有这两种，传别的后端返回 4000。 */
export type GraphLabel = 'Formula' | 'Herb'

/** 关系类型：目前只有"方 —组成→ 药"。 */
export type GraphRel = 'COMPOSED_OF'

export const GRAPH_LABEL_CN: Record<GraphLabel, string> = {
  Formula: '方剂',
  Herb: '药味'
}

export const GRAPH_REL_CN: Record<GraphRel, string> = {
  COMPOSED_OF: '组成'
}

/** 方剂节点的附加属性；药味节点是空对象。 */
export interface GraphNodeProps {
  /** 证候原文摘录（库内 232/245 有值，其余为 null 时后端不输出该键） */
  syndrome?: string
  /** 出处页码（当前库里 245/245 为空，字段留着备将来） */
  page?: string
}

export interface GraphNodeVO {
  /** 业务 ID：方剂 `f_1`、药味 `h_麻黄` */
  id: string
  label: GraphLabel
  name: string
  props?: GraphNodeProps
}

export interface GraphEdgeVO {
  source: string
  target: string
  rel: GraphRel
  /** COMPOSED_OF 上的剂量/单位/君臣佐使；库内只有 69/1315 条有剂量 */
  props?: {
    dose?: string
    unit?: string
    role?: string
  }
}

/** §15.1 单实体邻居（图谱探索页） */
export interface NeighborsVO {
  center: GraphNodeVO
  /** **不含 center**，按 label 再按 name 升序 */
  nodes: GraphNodeVO[]
  /** 只保留一端是 center 的边 */
  edges: GraphEdgeVO[]
  /** true = 邻居数超过 limit，前端提示"仅显示前 N 个" */
  truncated: boolean
}

/** §15.2 子图（批量渲染 / 相似度地图底图） */
export interface SubgraphVO {
  nodes: GraphNodeVO[]
  /** 两端必定都出现在 nodes 里 */
  edges: GraphEdgeVO[]
  stats: {
    nodeCount: number
    edgeCount: number
  }
  truncated: boolean
}

/** §15.3 方心子图（方剂详情页 / 图谱页中心块） */
export interface FormulaGraphVO {
  center: {
    id: string
    name: string
    /** 库内 86/245 有值，其余为空串或 null */
    alias: string | null
    /** 语料原文摘录 */
    syndromeText: string | null
    page: string | null
  }
  /** 按库内 seq 升序 */
  herbs: Array<{
    id: string
    name: string
    seq: number
    /** 字符串剂量（如 "3"），多数为 null */
    dose: string | null
    unit: string | null
    /** 君 / 臣 / 佐 / 使，当前库内全为空 */
    role: string | null
  }>
  /** true = 该方药味缺失或含解析残留（脏药名），前端必须提示"药味可能不完整" */
  herbsIncomplete: boolean
  /**
   * 药味交集最大的成方，按 jaccard 降序、最多 5 条。
   * **只能用"组成相近 ≠ 同一方"表述**，不得写成"同类方"或推断功效（设计红线）。
   */
  relatedFormulas: Array<{
    id: string
    name: string
    sharedHerbs: string[]
    jaccard: number
  }>
  /** 免责声明，原样展示 */
  notice: string
}

/** §15.4 两实体之间的路径 */
export interface GraphPathVO {
  /** false **不是错误**：显示"两实体之间最多 N 跳内无关联" */
  found: boolean
  paths: Array<{
    nodes: GraphNodeVO[]
    edges: GraphEdgeVO[]
    length: number
  }>
  /** 人类可读说明，如「经共享药味「桂枝」相连（2 跳）」 */
  explanation: string
}

/** §15.5 相似度地图坐标 */
export interface GraphMapVO {
  /** 一期只有 composition（药味 Jaccard） */
  metric: 'composition'
  /**
   * x/y 已归一化到 0~1，由服务端确定性计算（同一 version 反复请求完全一致）。
   * 坐标轴**没有语义**，不要拿 x/y 做数值解释。
   */
  points: Array<{
    id: string
    label: GraphLabel
    name: string
    x: number
    y: number
    /** 配色分组（c1、c2…）：同色 = 药味重合度高的一群，不代表证型/功效 */
    cluster: string
  }>
  /** 计算版本（口径 + 数据指纹），同版本必须可复现同一张图 */
  version: string
  truncated: boolean
}

export interface NeighborsQuery {
  /** 实体名或业务 ID（麻黄汤 / f_1 / 麻黄 / h_麻黄） */
  entity: string
  label?: GraphLabel
  /** 1~3；**超过 3 后端返回 4000**（契约 §15.1 明写，不是夹紧） */
  hops?: number
  /** 默认 50，最大 200 */
  limit?: number
}

export interface SubgraphQuery {
  /** 起点实体，逗号分隔最多 5 个；**不传 = 全图**（受 limit 限制） */
  entity?: string
  label?: GraphLabel
  /** 1~3，默认 2（越界会被夹紧，不报错） */
  hops?: number
  /** 只要这些节点类型，逗号分隔，默认两者都要 */
  types?: string
  /** 节点上限，默认 200，最大 500 */
  limit?: number
}

export interface GraphPathQuery {
  from: string
  to: string
  /** 1~4，默认 3 */
  maxHops?: number
  /** 默认 3，最大 5 */
  limit?: number
}

export interface GraphMapQuery {
  /** 默认 composition；传别的后端返回 4000 */
  metric?: 'composition'
  /** 点数，默认 200，最大 500 */
  limit?: number
  /** 可选：限定某目录节点（含子节点）下的方剂 */
  nodeId?: string
}

/** 15.1 单实体邻居 */
export function getGraphNeighbors(q: NeighborsQuery) {
  return request.get<never, NeighborsVO>('/biz/graph/neighbors', { params: q })
}

/** 15.2 子图 */
export function getGraphSubgraph(q: SubgraphQuery = {}) {
  return request.get<never, SubgraphVO>('/biz/graph/subgraph', { params: q })
}

/**
 * 15.3 方心子图。
 *
 * @param idOrName 方剂 ID（`f_1`，也接受裸 `1`）**或方名**（`麻黄汤`）。
 *                 方名重名时后端返回 4000 并给出候选 ID（库里确有同名不同方，如两首「葛根汤」），
 *                 所以路径里统一 encode，别自己拼字符串。
 */
export function getGraphFormula(idOrName: string) {
  return request.get<never, FormulaGraphVO>(`/biz/graph/formula/${encodeURIComponent(idOrName)}`)
}

/** 15.4 两实体之间的路径 */
export function getGraphPath(q: GraphPathQuery) {
  return request.get<never, GraphPathVO>('/biz/graph/path', { params: q })
}

/** 15.5 相似度地图坐标 */
export function getGraphMap(q: GraphMapQuery = {}) {
  return request.get<never, GraphMapVO>('/biz/graph/map', { params: q })
}

/**
 * 从错误对象里挖 HTTP 状态码。
 *
 * 为什么要兜底解析 message：`api/request.ts` 的响应拦截器把 axios 错误重新包成了
 * `new Error(msg)`，**丢掉了 `error.response`**，所以这类错误上没有 `status` 可取，
 * 只能从 "Request failed with status code 404" 这样的 message 里退回来。
 * 哪天拦截器改成把 status 挂到 Error 上，这个函数的第一个分支就会自动生效。
 */
function httpStatus(e: unknown): number | undefined {
  const direct = (e as { status?: unknown })?.status
  if (typeof direct === 'number') return direct
  const fromResp = (e as { response?: { status?: unknown } })?.response?.status
  if (typeof fromResp === 'number') return fromResp
  const matched = e instanceof Error ? /status code (\d{3})/.exec(e.message) : null
  return matched ? Number(matched[1]) : undefined
}

/** 后端 R.msg（或拦截器转好的 Error.message），拿不到返回 undefined。 */
function backendMsg(e: unknown): string | undefined {
  const fromResp = (e as { response?: { data?: { msg?: unknown } } })?.response?.data?.msg
  if (typeof fromResp === 'string' && fromResp) return fromResp
  if (e instanceof Error && e.message && !/status code \d{3}/.test(e.message)) return e.message
  return undefined
}

/** 图谱接口是否「尚未上线」（BFF 那层还没做）。404/501/405 都算。 */
export function isGraphNotImplemented(e: unknown): boolean {
  const status = httpStatus(e)
  return status === 404 || status === 501 || status === 405
}

/**
 * 把图谱接口错误压成一句能指导下一步的话（页面直接显示）。
 *
 * 404 有两种，靠后端的 `R.msg` 区分：
 *   · 有 msg（如「实体不存在」）→ 是 4040，参数本身没问题，提示改传参；
 *   · 没 msg（Spring 默认 404 体）→ 是 BFF 那层还没实现，提示等 §15.6 步骤 2。
 */
export function graphErrMsg(e: unknown): string {
  const status = httpStatus(e)
  const msg = backendMsg(e)
  if (status === 400) return msg || '参数不合法（4000）：检查 label / hops，或方名重名时改用 ID'
  if (status === 404) {
    return msg || '图谱接口尚未上线（BFF /api/biz/graph 未实现，见 09 契约 §15.6 步骤 2）'
  }
  if (status === 500) return msg || '图谱服务异常（5000）：确认 svc-graph :8085 与 Neo4j/PG 已启动'
  if (status === 501 || status === 405) return '图谱接口尚未上线（BFF /api/biz/graph 未实现）'
  return msg || '请求失败'
}
