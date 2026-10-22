/**
 * 域3 页面示意数据。
 *
 * ⚠️ 这里的数据是**占位**，不是真实图谱/治理数据，页面上必须显式标注。
 * 替换来源（按任务顺序）：
 *   - 图谱 / 方心子图 / 相似度地图 → `svc-graph` 的 `/internal/graph/**`（:8085，尚未建）
 *     经 BFF 暴露为 `/api/biz/graph/**`，或由 Agent 包一层 `/api/agent/graph/**`。
 *   - 治理后台 / 复核 / OCR 疑点 → `svc-governance` 的 `/internal/governance/**`（:8087，尚未建）。
 *
 * 结构照 `project_plan/prototype/assets/mock.js` 的 graph 段（10 节点 12 边），
 * 这样接真数据时只换数据源，组件不用动。
 */

export type NodeLabel = 'Formula' | 'Herb' | 'Syndrome' | 'Symptom'

export interface GNode {
  id: string
  label: NodeLabel
  name: string
  x: number
  y: number
  r: number
}

export interface GEdge {
  from: string
  to: string
  rel: 'COMPOSED_OF' | 'INDICATES' | 'MODIFIES' | 'SIMILAR_TO' | 'MANIFESTS'
}

/** 节点类型配色（与 theme.css 的色板一致，新增类型请复用这套 token） */
export const NODE_STYLE: Record<NodeLabel, { fill: string; stroke: string; text: string; cs: string }> = {
  Formula: { fill: '#E6F2EF', stroke: '#2E7D6F', text: '#1F5C52', cs: 'primary' },
  Herb: { fill: '#EAF2FC', stroke: '#3B7DD8', text: '#2A5DA0', cs: 'info' },
  Syndrome: { fill: '#FBEDE7', stroke: '#D9724E', text: '#B4552F', cs: 'accent' },
  Symptom: { fill: '#E9F3F2', stroke: '#4F8A8B', text: '#376566', cs: '' }
}

export const NODE_LABEL_CN: Record<NodeLabel, string> = {
  Formula: '方剂',
  Herb: '药味',
  Syndrome: '证候',
  Symptom: '症状'
}

export const DEMO_GRAPH: { nodes: GNode[]; edges: GEdge[] } = {
  nodes: [
    { id: 'mahuang', label: 'Formula', name: '麻黄汤', x: 400, y: 240, r: 34 },
    { id: 'guizhi', label: 'Formula', name: '桂枝汤', x: 250, y: 380, r: 30 },
    { id: 'gegen', label: 'Formula', name: '葛根汤', x: 570, y: 380, r: 30 },
    { id: 'ma', label: 'Herb', name: '麻黄', x: 250, y: 120, r: 22 },
    { id: 'gui', label: 'Herb', name: '桂枝', x: 560, y: 140, r: 22 },
    { id: 'xingren', label: 'Herb', name: '杏仁', x: 120, y: 240, r: 20 },
    { id: 'gancao', label: 'Herb', name: '炙甘草', x: 680, y: 240, r: 20 },
    { id: 'synd', label: 'Syndrome', name: '太阳伤寒表实', x: 400, y: 90, r: 30 },
    { id: 'sym1', label: 'Symptom', name: '无汗', x: 250, y: 500, r: 20 },
    { id: 'sym2', label: 'Symptom', name: '脉浮紧', x: 570, y: 500, r: 20 }
  ],
  edges: [
    { from: 'mahuang', to: 'ma', rel: 'COMPOSED_OF' },
    { from: 'mahuang', to: 'gui', rel: 'COMPOSED_OF' },
    { from: 'mahuang', to: 'xingren', rel: 'COMPOSED_OF' },
    { from: 'mahuang', to: 'gancao', rel: 'COMPOSED_OF' },
    { from: 'mahuang', to: 'synd', rel: 'INDICATES' },
    { from: 'guizhi', to: 'synd', rel: 'INDICATES' },
    { from: 'mahuang', to: 'gegen', rel: 'MODIFIES' },
    { from: 'guizhi', to: 'mahuang', rel: 'SIMILAR_TO' },
    { from: 'mahuang', to: 'sym1', rel: 'MANIFESTS' },
    { from: 'mahuang', to: 'sym2', rel: 'MANIFESTS' },
    { from: 'gegen', to: 'gui', rel: 'COMPOSED_OF' },
    { from: 'guizhi', to: 'gui', rel: 'COMPOSED_OF' }
  ]
}

export const REL_CN: Record<GEdge['rel'], string> = {
  COMPOSED_OF: '组成',
  INDICATES: '主治',
  MODIFIES: '加减化裁',
  SIMILAR_TO: '相似',
  MANIFESTS: '表现'
}

/** 路由参数可能是 ID（mahuang）也可能是中文名（麻黄汤），统一解析成 ID。 */
export function resolveNodeId(nameOrId: string): string {
  const hit = DEMO_GRAPH.nodes.find((n) => n.id === nameOrId || n.name === nameOrId)
  return hit ? hit.id : nameOrId
}

/** 取某个节点 1~2 跳邻居子图（真接口 `svc-graph /neighbors` 的本地模拟版）。 */
export function neighborSubgraph(
  rawId: string,
  hops: 1 | 2 = 2
): { nodes: GNode[]; edges: GEdge[]; center: GNode | null } {
  const centerId = resolveNodeId(rawId)
  const byId = new Map(DEMO_GRAPH.nodes.map((n) => [n.id, n]))
  const center = byId.get(centerId) ?? null
  if (!center) return { nodes: [], edges: [], center: null }

  const keep = new Set<string>([centerId])
  let frontier = [centerId]
  for (let h = 0; h < hops; h++) {
    const next: string[] = []
    for (const e of DEMO_GRAPH.edges) {
      if (frontier.includes(e.from) && !keep.has(e.to)) {
        keep.add(e.to)
        next.push(e.to)
      } else if (frontier.includes(e.to) && !keep.has(e.from)) {
        keep.add(e.from)
        next.push(e.from)
      }
    }
    frontier = next
  }

  // 以中心为原点重新做环形布局：中心居中，其余按原角度分布，避免子图挤在一起
  const others = [...keep].filter((id) => id !== centerId)
  const nodes = DEMO_GRAPH.nodes
    .filter((n) => keep.has(n.id))
    .map((n) => {
      if (n.id === centerId) return { ...n, x: 430, y: 280, r: Math.max(n.r, 32) }
      const i = others.indexOf(n.id)
      const ang = (i / Math.max(others.length, 1)) * Math.PI * 2 - Math.PI / 2
      // 两圈：相邻的放内圈，外围的稍微散开，视觉上更像"方心子图"
      const ring = n.label === 'Herb' ? 150 : i % 2 === 0 ? 210 : 165
      return {
        ...n,
        x: Math.round(430 + Math.cos(ang) * ring),
        y: Math.round(280 + Math.sin(ang) * ring * 0.82),
        r: Math.min(n.r, 24)
      }
    })
  const edges = DEMO_GRAPH.edges.filter((e) => keep.has(e.from) && keep.has(e.to))
  return { nodes, edges, center }
}

/** 相似度地图：4 个"方剂星系"的固定投影坐标（真接口 `svc-graph /map` 的本地模拟版）。 */
export interface MapCluster {
  name: string
  note: string
  color: string
  points: Array<{ name: string; x: number; y: number; r: number }>
}

export const DEMO_MAP: MapCluster[] = [
  {
    name: '麻黄类',
    note: '辛温解表',
    color: '#2E7D6F',
    points: [
      { name: '麻黄汤', x: 268, y: 186, r: 32 },
      { name: '葛根汤', x: 322, y: 232, r: 27 },
      { name: '大青龙汤', x: 216, y: 244, r: 24 },
      { name: '小青龙汤', x: 300, y: 140, r: 24 },
      { name: '麻黄附子细辛汤', x: 372, y: 168, r: 20 }
    ]
  },
  {
    name: '桂枝类',
    note: '调和营卫',
    color: '#3B7DD8',
    points: [
      { name: '桂枝汤', x: 566, y: 168, r: 32 },
      { name: '桂枝加葛根汤', x: 626, y: 214, r: 24 },
      { name: '桂枝加厚朴杏子汤', x: 512, y: 214, r: 22 },
      { name: '桂枝新加汤', x: 592, y: 118, r: 20 }
    ]
  },
  {
    name: '清热类',
    note: '辛寒清气',
    color: '#D9724E',
    points: [
      { name: '白虎汤', x: 604, y: 396, r: 28 },
      { name: '白虎加人参汤', x: 664, y: 432, r: 22 },
      { name: '竹叶石膏汤', x: 548, y: 438, r: 20 }
    ]
  },
  {
    name: '补益类',
    note: '温中补虚',
    color: '#C8A96A',
    points: [
      { name: '理中丸', x: 246, y: 398, r: 27 },
      { name: '四逆汤', x: 186, y: 442, r: 22 },
      { name: '真武汤', x: 306, y: 442, r: 22 },
      { name: '小建中汤', x: 250, y: 340, r: 20 }
    ]
  }
]

/* ---------------- 治理后台示意数据 ---------------- */

export interface ReviewItem {
  id: string
  title: string
  type: '案例' | '方剂' | '条文'
  chapter: string
  submitter: string
  submittedAt: string
  status: 'pending' | 'passed' | 'rejected'
  reason?: string
}

export const DEMO_REVIEWS: ReviewItem[] = [
  {
    id: 'rv_1',
    title: '麻黄汤证 · 案例二',
    type: '案例',
    chapter: '伤寒·太阳病',
    submitter: 'editor_a',
    submittedAt: '今天 18:20',
    status: 'pending'
  },
  {
    id: 'rv_2',
    title: '葛根汤 剂量',
    type: '方剂',
    chapter: '伤寒·太阳病',
    submitter: 'editor_a',
    submittedAt: '今天 16:05',
    status: 'pending'
  },
  {
    id: 'rv_3',
    title: '白虎汤证 · 按语',
    type: '案例',
    chapter: '温病·气分',
    submitter: 'editor_b',
    submittedAt: '昨天 16:11',
    status: 'pending'
  },
  {
    id: 'rv_4',
    title: '桂枝汤证 · 案例一',
    type: '案例',
    chapter: '伤寒·太阳病',
    submitter: 'editor_a',
    submittedAt: '今天 20:02',
    status: 'passed'
  },
  {
    id: 'rv_5',
    title: '某方 · 剂量解析',
    type: '方剂',
    chapter: '伤寒·太阳病',
    submitter: 'editor_b',
    submittedAt: '今天 19:40',
    status: 'rejected'
  }
]

export interface IssueItem {
  id: string
  kind: '异体字' | '剂量' | '命名' | '粘连'
  title: string
  detail: string
  severity: 'err' | 'warn' | 'ok'
  resolved: boolean
}

export const DEMO_ISSUES: IssueItem[] = [
  {
    id: 'is_1',
    kind: '异体字',
    title: '异体字：芎劳',
    detail: '疑为「川芎」· 第 214 页',
    severity: 'err',
    resolved: false
  },
  {
    id: 'is_2',
    kind: '剂量',
    title: '「各等分」剂量未结构化',
    detail: '约 12 条 · 批 3/7/9',
    severity: 'warn',
    resolved: false
  },
  {
    id: 'is_3',
    kind: '命名',
    title: '大/小青龙汤 名称缩写',
    detail: '需展开为全称',
    severity: 'warn',
    resolved: false
  },
  {
    id: 'is_4',
    kind: '粘连',
    title: '当归芍药散 案例粘连',
    detail: '已修复',
    severity: 'ok',
    resolved: true
  }
]

export interface AuditItem {
  time: string
  operator: string
  action: '通过' | '驳回' | '提交复核'
  target: string
}

export const DEMO_AUDIT: AuditItem[] = [
  { time: '今天 20:02', operator: 'admin', action: '通过', target: '桂枝汤证 · 案例一' },
  { time: '今天 19:40', operator: 'admin', action: '驳回', target: '某方 · 剂量解析' },
  { time: '昨天 16:11', operator: 'editor01', action: '提交复核', target: '白虎汤证 · 按语' }
]
