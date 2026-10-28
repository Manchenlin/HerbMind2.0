import request from './request'

export interface HerbStat {
  herb: string
  count: number
  formulaCount: number
  ratio: number
}

export interface CountItem {
  key: string
  label: string
  count: number
  ratio: number
}

export interface Trend {
  books: CountItem[]
  chapters: CountItem[]
  totalUnits: number
  totalFormulas: number
  totalCases: number
  totalQuotes: number
}

export interface ResearchPack {
  packId: string
  generatedAt: string
  seed: string
  summary: Record<string, number | string>
  tables: Array<{ name: string; title: string; rows: unknown[] }>
  files: string[]
  params: Record<string, unknown>
}

/** 用药频次 Top-N */
export function getHerbs(limit = 20, bookId?: string) {
  return request.get<unknown, HerbStat[]>('/biz/insight/herbs', { params: { limit, bookId } })
}

/** 证候分布 */
export function getSyndrome(limit = 12) {
  return request.get<unknown, CountItem[]>('/biz/insight/syndrome', { params: { limit } })
}

/** 经典 / 章节分布 */
export function getTrend() {
  return request.get<unknown, Trend>('/biz/insight/trend')
}

/** 可复现研究包 */
export function createResearchPack(params: Record<string, unknown>) {
  return request.post<unknown, ResearchPack>('/biz/insight/research-pack', params)
}

/** 导出下载地址（浏览器直接下载，不经 axios） */
export function exportUrl(kind: string, format: 'csv' | 'json' = 'csv') {
  return `/api/biz/insight/export?kind=${encodeURIComponent(kind)}&format=${format}`
}
