import { describe, expect, it } from 'vitest'

import {
  CANVAS_H,
  CANVAS_W,
  MAP_MAX_COLORED,
  MAP_MIN_GROUP_SIZE,
  MAP_OTHERS_COLOR,
  layoutFormula,
  layoutMap,
  layoutNeighbors,
  mapGroups,
  nodeRadius
} from '../frontend/src/utils/graphLayout'
import type { FormulaGraphVO, GraphNodeVO, GraphMapVO, NeighborsVO } from '../frontend/src/api/graph'

/**
 * `src/utils/graphLayout.ts` 的单元测试。
 *
 * 这一层是纯函数，唯一职责是「真实接口的拓扑 → 画布坐标」，所以断言都落在**几何性质**上
 * （在画布内、不重叠、内圈比外圈近、/map 坐标不被重排），而不是死抠某个具体坐标值 ——
 * 常量微调不该让测试变脆，但布局退化（挤成一坨、跑出画布）必须被抓住。
 */

const CX = CANVAS_W / 2
const CY = CANVAS_H / 2

function formula(id: string, name = id): GraphNodeVO {
  return { id, label: 'Formula', name, props: {} }
}

function herb(id: string, name = id): GraphNodeVO {
  return { id, label: 'Herb', name, props: {} }
}

/** 点到画布中心的椭圆归一化距离：1 表示正好落在环上 */
function ellipseNorm(x: number, y: number, rx: number, ry: number): number {
  return Math.hypot((x - CX) / rx, (y - CY) / ry)
}

function dist(a: { x: number; y: number }, b: { x: number; y: number }): number {
  return Math.hypot(a.x - b.x, a.y - b.y)
}

describe('nodeRadius', () => {
  it('方剂比药味大，未登记的类型退回药味尺寸', () => {
    expect(nodeRadius('Formula')).toBe(32)
    expect(nodeRadius('Herb')).toBe(22)
    // 证候/症状尚未实体化；万一传进来也不能返回 undefined 把 SVG 画崩
    expect(nodeRadius('Syndrome')).toBe(22)
  })
})

describe('layoutNeighbors — 方剂为中心（麻黄汤：4 味药）', () => {
  const data: NeighborsVO = {
    center: formula('f_1', '麻黄汤'),
    nodes: [herb('h_麻黄', '麻黄'), herb('h_桂枝', '桂枝'), herb('h_杏仁', '杏仁'), herb('h_甘草', '甘草')],
    edges: [
      { source: 'f_1', target: 'h_麻黄', rel: 'COMPOSED_OF' },
      { source: 'f_1', target: 'h_桂枝', rel: 'COMPOSED_OF' },
      { source: 'f_1', target: 'h_杏仁', rel: 'COMPOSED_OF' },
      { source: 'f_1', target: 'h_甘草', rel: 'COMPOSED_OF' }
    ],
    truncated: false
  }

  it('中心节点固定在画布中心，节点总数 = 中心 + 邻居', () => {
    const { nodes } = layoutNeighbors(data)
    expect(nodes).toHaveLength(5)
    expect(nodes[0]).toMatchObject({ id: 'f_1', x: CX, y: CY, r: 32 })
  })

  it('邻居落在环上（椭圆归一化距离 ≈ 1），不会挤在中心', () => {
    const { nodes } = layoutNeighbors(data)
    for (const n of nodes.slice(1)) {
      // 只有一类邻居时应铺满外圈
      expect(ellipseNorm(n.x, n.y, CANVAS_W / 2 - 52, CANVAS_H / 2 - 52)).toBeCloseTo(1, 5)
    }
  })

  it('边原样映射为 from/to/rel，不改语义', () => {
    const { edges } = layoutNeighbors(data)
    expect(edges).toHaveLength(4)
    expect(edges[0]).toEqual({ from: 'f_1', to: 'h_麻黄', rel: 'COMPOSED_OF' })
  })
})

describe('layoutNeighbors — 药味为中心（桂枝：50 首方）', () => {
  const many = Array.from({ length: 50 }, (_, i) => formula(`f_${i + 1}`, `方${i + 1}`))
  const data: NeighborsVO = {
    center: herb('h_桂枝', '桂枝'),
    nodes: many,
    edges: many.map((n) => ({ source: n.id, target: 'h_桂枝', rel: 'COMPOSED_OF' as const })),
    truncated: true
  }

  it('51 个节点全部落在画布内（不画出边界）', () => {
    const { nodes } = layoutNeighbors(data)
    expect(nodes).toHaveLength(51)
    for (const n of nodes) {
      expect(n.x - n.r).toBeGreaterThanOrEqual(0)
      expect(n.x + n.r).toBeLessThanOrEqual(CANVAS_W)
      expect(n.y - n.r).toBeGreaterThanOrEqual(0)
      expect(n.y + n.r).toBeLessThanOrEqual(CANVAS_H)
    }
  })

  it('邻居之间不重叠：圆心距 ≥ 两半径之和', () => {
    const { nodes } = layoutNeighbors(data)
    const ring = nodes.slice(1)
    for (let i = 0; i < ring.length; i++) {
      for (let j = i + 1; j < ring.length; j++) {
        expect(dist(ring[i], ring[j])).toBeGreaterThanOrEqual(ring[i].r + ring[j].r)
      }
    }
  })

  it('节点太多时半径被压缩，但不小于可读下限 9', () => {
    const { nodes } = layoutNeighbors(data)
    const r = nodes[1].r
    expect(r).toBeLessThan(32)
    expect(r).toBeGreaterThanOrEqual(9)
  })
})

describe('layoutNeighbors — 双层环与空邻居', () => {
  it('药味在内圈、方剂在外圈：内圈更靠近中心', () => {
    const data: NeighborsVO = {
      center: formula('f_1', '麻黄汤'),
      nodes: [herb('h_麻黄', '麻黄'), herb('h_桂枝', '桂枝'), formula('f_2', '桂枝汤'), formula('f_3', '大青龙汤')],
      edges: [],
      truncated: false
    }
    const { nodes } = layoutNeighbors(data)
    const herbDist = Math.max(...nodes.filter((n) => n.label === 'Herb').map((n) => dist(n, nodes[0])))
    const formulaDist = Math.min(
      ...nodes.filter((n) => n.label === 'Formula' && n.id !== 'f_1').map((n) => dist(n, nodes[0]))
    )
    expect(herbDist).toBeLessThan(formulaDist)
  })

  it('没有任何邻居时只画中心节点，不抛异常', () => {
    const data: NeighborsVO = { center: formula('f_1', '麻黄汤'), nodes: [], edges: [], truncated: false }
    const { nodes, edges } = layoutNeighbors(data)
    expect(nodes).toHaveLength(1)
    expect(edges).toHaveLength(0)
  })
})

describe('layoutFormula — 方心子图', () => {
  const data: FormulaGraphVO = {
    center: { id: 'f_1', name: '麻黄汤', alias: null, syndromeText: '恶风寒、发热', page: null },
    herbs: [
      { id: 'h_麻黄', name: '麻黄', seq: 1, dose: null, unit: null, role: null },
      { id: 'h_桂枝', name: '桂枝', seq: 2, dose: null, unit: null, role: null }
    ],
    herbsIncomplete: false,
    relatedFormulas: [
      { id: 'f_3', name: '大青龙汤', sharedHerbs: ['麻黄', '桂枝'], jaccard: 0.5714 },
      { id: 'f_128', name: '葛根汤', sharedHerbs: ['桂枝'], jaccard: 0.4286 }
    ],
    notice: '仅比对药味组成'
  }

  it('中心 + 药味 + 相关方都上画布', () => {
    const { nodes } = layoutFormula(data)
    expect(nodes).toHaveLength(5)
    expect(nodes[0]).toMatchObject({ id: 'f_1', x: CX, y: CY })
  })

  it('只画「中心方 → 药味」的边，不给相关方造假边', () => {
    const { edges } = layoutFormula(data)
    expect(edges).toHaveLength(2)
    for (const e of edges) {
      expect(e.from).toBe('f_1')
      expect(e.rel).toBe('COMPOSED_OF')
      expect(e.to.startsWith('h_')).toBe(true)
    }
    // 「组成相近」不是图里的关系，一旦画出 f_3 的边就等于凭空造关系
    expect(edges.some((e) => e.to === 'f_3')).toBe(false)
  })

  it('药味为空时没有边', () => {
    const empty: FormulaGraphVO = { ...data, herbs: [], relatedFormulas: [] }
    const { nodes, edges } = layoutFormula(empty)
    expect(nodes).toHaveLength(1)
    expect(edges).toHaveLength(0)
  })
})

describe('layoutMap — 相似度地图', () => {
  const data: GraphMapVO = {
    metric: 'composition',
    points: [
      { id: 'f_1', label: 'Formula', name: '麻黄汤', x: 0, y: 0, cluster: 'c1' },
      { id: 'f_2', label: 'Formula', name: '桂枝汤', x: 1, y: 1, cluster: 'c2' }
    ],
    version: 'composition:v1:abc',
    truncated: false
  }

  it('0~1 坐标线性映射到画布内边距，不重排', () => {
    const [a, b] = layoutMap(data)
    expect(a.x).toBeCloseTo(46, 5)
    expect(a.y).toBeCloseTo(46, 5)
    expect(b.x).toBeCloseTo(CANVAS_W - 46, 5)
    expect(b.y).toBeCloseTo(CANVAS_H - 46, 5)
  })

  it('半径缩小到方心子图的一半以下（一屏要放 150+ 个点）', () => {
    const [a] = layoutMap(data)
    expect(a.r).toBeLessThan(32 * 0.5)
    expect(a.label).toBe('Formula')
  })

  it('cluster 原样保留，供分组配色使用', () => {
    const [a, b] = layoutMap(data)
    expect(a.cluster).toBe('c1')
    expect(b.cluster).toBe('c2')
  })
})

describe('mapGroups — 分组配色与图例', () => {
  it('规模降序排；达到门槛的组上色并给「第 N 组」', () => {
    const groups = mapGroups([
      ...Array(9).fill('c97'),
      'c3',
      'c3',
      'c7'
    ])
    expect(groups).toHaveLength(3)
    expect(groups[0]).toMatchObject({ key: 'c97', count: 9, listed: true, label: '第 1 组' })
    expect(groups[1]).toMatchObject({ key: 'c3', count: 2, listed: false, label: '其余小组' })
    expect(groups[1].color).toBe(MAP_OTHERS_COLOR)
    expect(groups[0].color).not.toBe(MAP_OTHERS_COLOR)
  })

  it('同规模时按 cluster 序号升序（保证配色可复现）', () => {
    const groups = mapGroups(['c10', 'c2', 'c10', 'c2', 'c2', 'c10'])
    expect(groups.map((g) => g.key)).toEqual(['c2', 'c10'])
    expect(groups[0].count).toBe(3)
  })

  it(`最多只给 ${MAP_MAX_COLORED} 组上色，其余统一灰，颜色不重复`, () => {
    const clusters: string[] = []
    for (let i = 1; i <= 12; i++) {
      clusters.push(...Array(MAP_MIN_GROUP_SIZE).fill(`c${i}`))
    }
    const groups = mapGroups(clusters)
    const listed = groups.filter((g) => g.listed)
    expect(listed).toHaveLength(MAP_MAX_COLORED)
    expect(new Set(listed.map((g) => g.color)).size).toBe(MAP_MAX_COLORED)
    expect(groups.slice(MAP_MAX_COLORED).every((g) => g.color === MAP_OTHERS_COLOR)).toBe(true)
  })

  it('组内方剂数不足门槛的组一律不上色', () => {
    const groups = mapGroups(['c1', 'c2', 'c2'])
    expect(groups.every((g) => !g.listed)).toBe(true)
  })

  it('空输入返回空数组，不抛异常', () => {
    expect(mapGroups([])).toEqual([])
  })
})
