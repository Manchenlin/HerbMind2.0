import request from './request'

/**
 * 练习（域2）。
 * 后端：BFF `/api/biz/train/**` → svc-training `/internal/training/**`。
 *
 * 题面接口**不返回方名**（先思后看），答案在提交后的 refText 里揭晓。
 */

export interface NodeOption {
  /** book_node.id —— 练习单元的 ref */
  id: string
  title: string
  /** 该单元的方证数 = 可出的题数 */
  formulaCount: number
  practiced: boolean
}

export interface BookOption {
  id: string
  title: string
  nodes: NodeOption[]
}

export interface RecentItem {
  sessionId: string
  nodeTitle: string
  mode: string
  /** 已格式化：今天 20:14 / 昨天 / 10-09 */
  time: string
  /** 该会话得分，未评为 null */
  score: number | null
  durationSeconds: number
  inWrongBook: boolean
}

export interface TrainOptions {
  books: BookOption[]
  modes: string[]
  recent: RecentItem[]
}

export interface PracticeQuestion {
  sessionId: string
  index: number
  total: number
  nodeId: string
  nodeTitle: string
  bookTitle: string
  caseId: string
  /** 症状描述 */
  symptoms: string
  /** 舌脉 */
  signs: string
  /** 审题提示（不含答案） */
  hint: string
}

export interface HerbItem {
  herb: string
  dose: number | null
  unit: string
}

export interface SubmitAnswerReq {
  sessionId: string
  syndrome: string
  treatment: string
  prescription: HerbItem[]
}

export interface AnswerScore {
  answerId: string
  total: number
  syndromeScore: number
  formulaScore: number
  treatmentScore: number
  hit: string[]
  miss: string[]
  extra: string[]
  refText: string
  /** rule = 确定性规则评分；agent = 大模型语义评分 */
  scoredBy: string
}

/** 练习台选项：可练的书 / 单元 / 模式 + 最近练习 */
export function getTrainOptions() {
  return request.get<unknown, TrainOptions>('/biz/train/options')
}

/** 开练习会话并取题面。formulaId 给定时固定出那道题（盲盒「我也答一遍」用） */
export function startSession(nodeRef: string, mode: string, formulaId?: string) {
  return request.post<unknown, PracticeQuestion>('/biz/train/session', null, {
    params: formulaId ? { nodeRef, mode, formulaId } : { nodeRef, mode }
  })
}

/** 提交作答 → 评分 */
export function submitAnswer(payload: SubmitAnswerReq) {
  return request.post<unknown, AnswerScore>('/biz/train/answer', payload)
}

/* --------------------------- 案例盲盒（/train/blindbox） --------------------------- */

export interface Blindbox {
  caseId: string
  title: string
  /** 案例原文（截断） */
  illness: string
  /** 舌脉 */
  exam: string
  /** 开会话用的单元 ID */
  nodeId: string
  nodeTitle: string
  bookTitle: string
  /** 仅用于「我也答一遍」，页面不展示 */
  formulaId: string
  /** 已练过的盲盒次数 */
  drawnCount: number
  avgScore: number | null
}

export interface BlindboxAnswer {
  formulaName: string
  syndromeText: string
  efficacy: string
  /** 原著处方，形如「麻黄 9g」 */
  prescription: string[]
  refText: string
}

/** 抽一个盲盒（只读，不建会话） */
export function drawBlindbox() {
  return request.post<unknown, Blindbox>('/biz/train/blindbox')
}

/** 揭晓原著答案 */
export function revealBlindbox(caseId: string, formulaId?: string) {
  return request.get<unknown, BlindboxAnswer>(`/biz/train/blindbox/${caseId}/answer`, {
    params: formulaId ? { formulaId } : {}
  })
}

/* --------------------------- 背诵打卡（/train/recite） --------------------------- */

export interface ReciteItem {
  quoteId: string
  articleNo: string | null
  classicName: string
  content: string
  plainText: string | null
  /** 起句提示（前 6 字），条文号缺失时靠它定位 */
  hint: string
  /** 去标点后的字数 */
  charCount: number
  /** 今天该复习（到期或从未背过） */
  due: boolean
  /** 对 / 基本对 / 不对，没背过为 null */
  lastResult: string | null
  reviewLabel: string | null
}

export interface ReciteData {
  items: ReciteItem[]
  stats: { total: number; due: number; mastered: number; streak: number }
}

export interface ReciteResult {
  score: number
  level: string
  matched: string[]
  missed: string[]
  standard: string
  nextReviewLabel: string
  mastered: boolean
  /** rule = 字面比对 */
  scoredBy: string
}

export function getRecite() {
  return request.get<unknown, ReciteData>('/biz/train/recite')
}

export function submitRecite(payload: { quoteId: string; text: string }) {
  return request.post<unknown, ReciteResult>('/biz/train/recite', payload)
}

/* --------------------------- 评分报告（/train/report/:id） --------------------------- */

export interface ReportRadar {
  key: string
  label: string
  value: number
}

export interface Report {
  answerId: string
  sessionId: string
  nodeTitle: string
  bookTitle: string
  formulaName: string
  caseId: string | null
  submittedLabel: string
  durationSeconds: number
  total: number
  syndromeScore: number
  formulaScore: number
  treatmentScore: number
  hit: string[]
  miss: string[]
  extra: string[]
  refText: string
  userSyndrome: string
  userTreatment: string
  userPrescription: string[]
  scoredBy: string
  /** 累计能力画像（不是这一次答题的） */
  radar: ReportRadar[]
}

export function getReport(answerId: string) {
  return request.get<unknown, Report>(`/biz/train/report/${answerId}`)
}
