import request from './request'
import type { Book, FormulaDetail } from './catalog'
import type { SearchHit } from './search'

export interface GraphNode {
  id: string
  type: string
  name: string
  level: number
}

export interface GraphEdge {
  source: string
  target: string
  rel: string
}

export interface GraphPreview {
  nodes: GraphNode[]
  edges: GraphEdge[]
  formulaId?: string
}

export interface Home {
  stats?: {
    books: number
    nodes: number
    formulas: number
    cases: number
    quotes: number
    vectors: number
  }
  books?: Book[]
  today?: FormulaDetail
  graph?: GraphPreview
  graphSource?: string
  hotKeywords?: string[]
  /** 首页「大家都在查」：search 聚合结果（A4 要求 catalog + search + graph） */
  hotHits?: SearchHit[]
  /** 本次降级的分区（如 search 未启动） */
  degraded?: string[]
}

/** 首页聚合（catalog + graph 预览） */
export function getHome() {
  return request.get<unknown, Home>('/biz/home')
}
