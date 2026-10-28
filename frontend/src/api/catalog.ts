import request from './request'

/** ===== 类型（与后端 DTO 一一对应，字段全部 camelCase） ===== */

export interface BookTreeNode {
  id: string
  title: string
  /** chapter / section / category */
  nodeType: string
  children: BookTreeNode[]
}

export interface LinkRef {
  id: string
  name: string
}

export interface Herb {
  name: string
  dose?: number
  unit?: string
  /** 君 / 臣 / 佐 / 使 */
  role?: string
  seq?: number
}

export interface Book {
  id: string
  title: string
  bookType?: string
  bookTypeLabel?: string
  author?: string
  dynasty?: string
  edition?: string
  sourceLicense?: string
  ingestStatus?: string
  statusLabel?: string
  createdAt?: string
  unitCount?: number
  nodeCount?: number
  formulaCount?: number
  caseCount?: number
}

export interface QuoteRef {
  id: string
  articleNo?: string
  classicName?: string
  content?: string
  plainText?: string
  page?: string
  label?: string
}

export interface CaseBrief {
  id: string
  title?: string
  mainFormulaId?: string
  mainFormulaName?: string
  syndrome?: string
  page?: string
}

export interface FormulaBrief {
  id: string
  name: string
  efficacy?: string
  syndrome?: string
  page?: string
  nodeId?: string
  nodeTitle?: string
  herbs?: Herb[]
}

export interface FormulaDetail {
  id: string
  name: string
  pinyin?: string
  alias?: string
  efficacy?: string
  syndrome?: string
  sourceText?: string
  page?: string
  nodeId?: string
  nodeTitle?: string
  bookId?: string
  bookTitle?: string
  classicName?: string
  chapter?: string
  herbs: Herb[]
  quotes: QuoteRef[]
  cases: CaseBrief[]
  related: FormulaBrief[]
}

export interface CaseSection {
  id: string
  kind?: string
  content?: string
  seq: number
}

export interface CaseDetail {
  id: string
  title?: string
  unitType?: string
  mainFormulaId?: string
  mainFormulaName?: string
  syndrome?: string
  page?: string
  bookId?: string
  bookTitle?: string
  chapter?: string
  sections: CaseSection[]
  quotes: QuoteRef[]
  /** 同一主方下的其它医案（案例一/二/三 切换） */
  siblings?: CaseBrief[]
}

export interface QuoteItem {
  no?: string
  text: string
  label?: string
  formulas?: LinkRef[]
  cases?: LinkRef[]
}

export interface QuoteDetail {
  id: string
  articleNo?: string
  classicId?: string
  classicName?: string
  bookId?: string
  bookTitle?: string
  content?: string
  plainText?: string
  page?: string
  label?: string
  items: QuoteItem[]
  formulas: LinkRef[]
  cases: LinkRef[]
}

export interface NodeDetail {
  node: BookTreeNode
  bookId?: string
  bookTitle?: string
  classicId?: string
  parentId?: string
  pathText?: string
  breadcrumb: LinkRef[]
  formulas: FormulaBrief[]
  cases: CaseBrief[]
  quotes: QuoteRef[]
  childCount: number
}

export interface ImportStatus {
  importId: string
  bookId?: string
  title?: string
  status?: string
  message?: string
  createdAt?: string
}

export interface ImportRequest {
  title: string
  bookType?: string
  author?: string
  dynasty?: string
  sourceLicense?: string
  visibility?: string
  generateEmbedding?: boolean
  extractHerbs?: boolean
  note?: string
}

/** ===== 接口（域1） ===== */

/** 典籍目录树 */
export function getLibraryTree(bookId = 'bk_1') {
  return request.get<unknown, BookTreeNode[]>('/biz/library/tree', { params: { bookId } })
}

/** 书架 / 语料列表 */
export function getBooks() {
  return request.get<unknown, Book[]>('/biz/catalog/books')
}

/** 目录节点详情（节点 + 其下 方剂 / 医案 / 条文 + 面包屑） */
export function getNodeDetail(id: string) {
  return request.get<unknown, NodeDetail>(`/biz/catalog/node/${encodeURIComponent(id)}`)
}

/** 方剂详情页 */
export function getFormula(id: string) {
  return request.get<unknown, FormulaDetail>(`/biz/formula/${encodeURIComponent(id)}/page`)
}

/** 医案详情页 */
export function getCase(id: string) {
  return request.get<unknown, CaseDetail>(`/biz/case/${encodeURIComponent(id)}/page`)
}

/** 条文详情页 */
export function getQuote(id: string) {
  return request.get<unknown, QuoteDetail>(`/biz/quote/${encodeURIComponent(id)}/page`)
}

/** 导入语料（UGC → 治理审核） */
export function importBook(body: ImportRequest) {
  return request.post<unknown, ImportStatus>('/biz/catalog/import', body)
}

/** 导入状态 */
export function getImportStatus(importId: string) {
  return request.get<unknown, ImportStatus>(`/biz/catalog/import/${encodeURIComponent(importId)}`)
}
