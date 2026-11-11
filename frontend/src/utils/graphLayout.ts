import type {
  FormulaGraphVO,
  GraphEdgeVO,
  GraphMapVO,
  GraphNodeVO,
  NeighborsVO
} from '@/api/graph'
import type { GEdge, GNode } from '@/mock/domain3'

/**
 * 真实图谱数据 → 画布坐标。
 *
 * ## 为什么要这一层
 *
 * `GraphCanvas` 只按每个节点自带的 `x/y/r` 画点，**不做布局**。而 `/api/biz/graph/**`
 * 除 `/map` 外都只返回拓扑（节点 + 边），没有坐标。所以三个页面各画一遍布局必然写歪，
 * 统一收在这里。
 *
 * ## 两条硬约束
 *
 * 1. **`/map` 的坐标直接用，不重排**：后端保证「同一 version 给出同一张图」，
 *    前端若自己再算一遍就破坏了这个承诺（每次刷新图形乱跳，没法讲解和截图）。
 * 2. **只有 Formula / Herb 两类节点**：证候、症状尚未实体化，布局里不要为它们留位置。
 */

/** 画布逻辑尺寸，与 GraphCanvas 内部 viewBox 保持一致 */
export const CANVAS_W = 860
export const CANVAS_H = 560

/** 节点半径：方剂大、药味小，靠尺寸区分层级 */
const RADIUS: Record<string, number> = { Formula: 32, Herb: 22 }

/** 环能用的最大椭圆半轴：留出节点半径与边距，保证圆不贴画布边 */
const MAX_RX = CANVAS_W / 2 - 52
const MAX_RY = CANVAS_H / 2 - 52

/** 内圈相对外圈的缩放：药味圈要明显小于外圈，两层才分得开 */
const INNER_SCALE = 0.52

/** 相邻两个节点之间至少空出的像素，避免圆挨圆糊成一条粗环 */
const NODE_GAP = 14

/** 圆的最小半径：再小名字就没法看了，宁可挤一点 */
const MIN_NODE_R = 9

export function nodeRadius(label: string): number {
  return RADIUS[label] ?? 22
}

function toGNode(node: GraphNodeVO, x: number, y: number, r: number): GNode {
  return { id: node.id, label: node.label, name: node.name, x, y, r }
}

function toGEdges(edges: GraphEdgeVO[]): GEdge[] {
  return edges.map((e) => ({ from: e.source, to: e.target, rel: e.rel }))
}

/**
 * 椭圆周长（Ramanujan 近似）。
 *
 * 为什么用椭圆不是圆：画布是 860×560，圆形环的半径被短边卡死在 280 以内，
 * 长边两侧会空掉一大片；椭圆能把横向空间用上，同样的环能多放 30% 的节点。
 */
function ellipsePerimeter(rx: number, ry: number): number {
  const h = ((rx - ry) / (rx + ry)) ** 2
  return Math.PI * (rx + ry) * (1 + (3 * h) / (10 + Math.sqrt(4 - 3 * h)))
}

/**
 * 环上要摆 count 个节点时，每个圆能有多大。
 *
 * 相邻格位间距 = 周长 / count，圆直径必须小于「间距 − NODE_GAP」，否则相互压住。
 * 药名「桂枝」「麻黄汤」在圆里只放得下 2~4 字，所以半径缩到 9 就不再缩了 ——
 * 再多邻居就只能压（页面上用 `truncated` 提示"仅显示前 N 个"）。
 */
function fitRadius(count: number, rx: number, ry: number, base: number): number {
  if (count <= 0) return base
  const spacing = ellipsePerimeter(rx, ry) / count
  return Math.max(MIN_NODE_R, Math.min(base, (spacing - NODE_GAP) / 2))
}

/** 把一组节点均匀摊在椭圆环上，从正上方开始顺时针排 */
function placeRing(
  nodes: GraphNodeVO[],
  cx: number,
  cy: number,
  rx: number,
  ry: number,
  r: number,
  startAngle = -Math.PI / 2
): GNode[] {
  const step = (Math.PI * 2) / Math.max(nodes.length, 1)
  return nodes.map((n, i) => {
    const angle = startAngle + i * step
    return toGNode(n, cx + Math.cos(angle) * rx, cy + Math.sin(angle) * ry, r)
  })
}

/** 画布中心 */
function centerOf(): { cx: number; cy: number } {
  return { cx: CANVAS_W / 2, cy: CANVAS_H / 2 }
}

/**
 * 15.1 邻居页：中心 + 药味（内圈）+ 方剂（外圈）。
 *
 * 两种邻居都在时用双层环：药味通常 4~8 味、方剂可能有几十首，
 * 混在一圈里会挤成一团，分层后"这味药组成了哪些方"一眼能看出来。
 */
export function layoutNeighbors(data: NeighborsVO): { nodes: GNode[]; edges: GEdge[] } {
  const { cx, cy } = centerOf()
  const herbs = data.nodes.filter((n) => n.label === 'Herb')
  const others = data.nodes.filter((n) => n.label !== 'Herb')

  const nodes: GNode[] = [toGNode(data.center, cx, cy, nodeRadius(data.center.label))]

  if (others.length === 0) {
    // 只有一类邻居：直接摊满外圈，别都挤在内圈
    const r = fitRadius(herbs.length, MAX_RX, MAX_RY, nodeRadius('Herb'))
    nodes.push(...placeRing(herbs, cx, cy, MAX_RX, MAX_RY, r))
  } else {
    if (herbs.length) {
      const rx = MAX_RX * INNER_SCALE
      const ry = MAX_RY * INNER_SCALE
      const r = fitRadius(herbs.length, rx, ry, nodeRadius('Herb'))
      nodes.push(...placeRing(herbs, cx, cy, rx, ry, r))
    }
    const r = fitRadius(others.length, MAX_RX, MAX_RY, nodeRadius('Formula'))
    // 外圈错开半格，避免连线正好压在某个内圈节点的正上方
    const offset = others.length > 1 ? Math.PI / others.length : 0
    nodes.push(...placeRing(others, cx, cy, MAX_RX, MAX_RY, r, -Math.PI / 2 + offset))
  }

  return { nodes, edges: toGEdges(data.edges) }
}

/**
 * 15.3 方心子图页：中心方 + 药味（内圈）+ 组成相近方（外圈）。
 *
 * 外圈用的是 `relatedFormulas` 而不是图边，所以这里要自己造边 ——
 * 它们的语义是「组成相近」，不是 `COMPOSED_OF`，画布上统一标成组成关系会误导，
 * 因此**不造边**，只把相关方作为孤立节点摆在环上，页面上另用列表说明相似度。
 */
export function layoutFormula(data: FormulaGraphVO): { nodes: GNode[]; edges: GEdge[] } {
  const { cx, cy } = centerOf()
  // 中心方的 DTO 与 GraphNodeVO 不同（没有 label / props），这里补齐后复用同一套布局
  const centerNode: GraphNodeVO = {
    id: data.center.id,
    label: 'Formula',
    name: data.center.name,
    props: data.center.syndromeText ? { syndrome: data.center.syndromeText } : {}
  }
  const nodes: GNode[] = [toGNode(centerNode, cx, cy, nodeRadius('Formula'))]

  const herbNodes: GraphNodeVO[] = data.herbs.map((h) => ({
    id: h.id,
    label: 'Herb',
    name: h.name,
    props: {}
  }))
  if (herbNodes.length) {
    const rx = MAX_RX * INNER_SCALE
    const ry = MAX_RY * INNER_SCALE
    nodes.push(...placeRing(herbNodes, cx, cy, rx, ry, fitRadius(herbNodes.length, rx, ry, nodeRadius('Herb'))))
  }

  // 相关方只做外圈点缀，不参与边的拓扑
  const relatedNodes: GraphNodeVO[] = data.relatedFormulas.map((f) => ({
    id: f.id,
    label: 'Formula',
    name: f.name,
    props: {}
  }))
  if (relatedNodes.length) {
    const r = fitRadius(relatedNodes.length, MAX_RX, MAX_RY, nodeRadius('Formula'))
    nodes.push(...placeRing(relatedNodes, cx, cy, MAX_RX, MAX_RY, r, -Math.PI / 2))
  }

  // 边只画「中心方 → 药味」，这是库里真实存在的关系
  const edges: GEdge[] = herbNodes.map((h) => ({ from: data.center.id, to: h.id, rel: 'COMPOSED_OF' }))
  return { nodes, edges }
}

/**
 * 15.5 地图页：**直接使用后端坐标**，只做 0~1 → 画布像素的线性映射。
 *
 * 半径比方心子图小得多：地图上一屏要放 150+ 个方，用 32×0.62≈20 的圆会互相盖住，
 * 名字全靠悬停才看得见。这里缩到 0.45，悬停时再放大。
 */
export function layoutMap(data: GraphMapVO): Array<GNode & { cluster: string }> {
  const pad = 46
  const w = CANVAS_W - pad * 2
  const h = CANVAS_H - pad * 2
  return data.points.map((p) => ({
    id: p.id,
    label: p.label,
    name: p.name,
    x: pad + p.x * w,
    y: pad + p.y * h,
    r: nodeRadius(p.label) * 0.45,
    cluster: p.cluster
  }))
}

/**
 * 地图分组配色。
 *
 * ## 为什么不是"一组一个颜色"
 *
 * 后端按药味 Jaccard 阈值阶梯切连通分量（`CompositionAnalytics.clusters`），阈值逐级
 * 升到 0.9 仍拆不开就整块保留 —— 结果是 245 首方里有 100 多个组、绝大多数只有 1~2 首。
 * 一组一色的话：图例 100+ 行、颜色循环复用、同色不同组，图例本身就变成噪音。
 *
 * ## 所以只给"规模够大的组"上色，其余统一灰
 *
 * 图例里出现的每一种颜色都确实对应图上的一组点，灰色明确标注为"其余小组"。
 * 这是**画法**上的取舍，不改数据：每首方的 cluster 值仍原样保留在抽屉里。
 */
const PALETTE = [
  '#2E7D6F',
  '#3B7DD8',
  '#D9724E',
  '#8A6FB0',
  '#C9A227',
  '#4F8A8B',
  '#B0563F',
  '#5C8A3B'
]

/** 其余小组（组内方剂太少）统一用的中性色 */
export const MAP_OTHERS_COLOR = '#8B949E'

/** 最多给几个组上色（与 PALETTE 长度对齐，超过就没色可分了） */
export const MAP_MAX_COLORED = PALETTE.length

/** 进图例的最小规模：少于这个数的组不单独上色 */
export const MAP_MIN_GROUP_SIZE = 3

export interface MapGroupInfo {
  /** 后端 cluster 原值（c1、c2…） */
  key: string
  /** 组内方剂数 */
  count: number
  color: string
  /** 是否上色进图例 */
  listed: boolean
  /**
   * 展示名。**不用后端的 c 编号**：c97、c110 这种对读者没有意义（图上并没有 97 个
   * 可见分组），所以按"规模排名"重编号，只对进图例的组给名字。
   */
  label: string
}

/**
 * 按 cluster 值统计分组，并按规模降序给出配色与图例信息。
 *
 * 排序用「规模降序 + cluster 序号升序」两级，保证同一份数据每次得到同一套颜色。
 */
export function mapGroups(clusters: string[]): MapGroupInfo[] {
  const counts = new Map<string, number>()
  for (const c of clusters) counts.set(c, (counts.get(c) ?? 0) + 1)

  const idOf = (key: string): number => {
    const n = Number(key.replace(/^c/, ''))
    return Number.isFinite(n) ? n : Number.MAX_SAFE_INTEGER
  }

  const sorted = Array.from(counts.entries()).sort(
    (a, b) => b[1] - a[1] || idOf(a[0]) - idOf(b[0])
  )

  let colored = 0
  return sorted.map(([key, count]) => {
    const listed = count >= MAP_MIN_GROUP_SIZE && colored < MAP_MAX_COLORED
    if (listed) colored += 1
    return {
      key,
      count,
      color: listed ? PALETTE[colored - 1] : MAP_OTHERS_COLOR,
      listed,
      label: listed ? `第 ${colored} 组` : '其余小组'
    }
  })
}
