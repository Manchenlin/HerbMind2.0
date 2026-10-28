import request from './request'

export interface SearchHit {
  id: string
  /** formula / case / quote */
  refType: string
  refId: string
  title?: string
  snippet?: string
  score: number
  bookId?: string
  bookTitle?: string
  classic?: string
  chapter?: string
  section?: string
  page?: string
  herbs?: string[]
  /** vector / fulltext / fuzzy / quote */
  matchedBy?: string[]
  meta?: Record<string, unknown>
}

export interface Facets {
  types: Record<string, number>
  classics: Record<string, number>
  books: Record<string, number>
}

export interface SearchResult {
  list: SearchHit[]
  total: number
  page: number
  size: number
  /** hybrid / fulltext / fuzzy / browse */
  mode?: string
  tookMs?: number
  facets: Facets
}

export interface SearchRequest {
  q: string
  type?: string
  bookId?: string
  herb?: string
  page?: number
  size?: number
}

export interface QuoteIndexItem {
  quoteId: string
  classicName?: string
  articleNo?: string
  text: string
  page?: string
  formulas: Array<{ id: string; name: string }>
  cases: Array<{ id: string; name: string }>
}

export interface QuoteIndexResult {
  list: QuoteIndexItem[]
  total: number
  page: number
  size: number
}

/** 多维 / 关键词检索（分面） */
export function search(q: string, opts: Omit<SearchRequest, 'q'> = {}) {
  return request.get<unknown, SearchResult>('/biz/search', {
    params: { q, type: opts.type, bookId: opts.bookId, herb: opts.herb, page: opts.page, size: opts.size }
  })
}

/** 语义检索（混合召回） */
export function semanticSearch(body: SearchRequest) {
  return request.post<unknown, SearchResult>('/biz/search/semantic', body)
}

/** 条文反向索引 */
export function getQuoteIndex(q: string, page = 1, size = 20, bookId?: string) {
  return request.get<unknown, QuoteIndexResult>('/biz/search/quote-index', {
    params: { q, page, size, bookId }
  })
}

/** 分面统计 */
export function getFacets(q = '', bookId?: string) {
  return request.get<unknown, Facets>('/biz/search/facets', { params: { q, bookId } })
}
