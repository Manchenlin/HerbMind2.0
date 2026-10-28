import request from './request'
import type { UserDto } from './user'

/**
 * 「我的 · 总览」（域2）。
 * 后端：BFF `GET /api/biz/me/dashboard`（聚合 svc-identity + svc-training）。
 * 字段全部 camelCase，与 09 契约一致。
 */

export interface MeStats {
  /** 累计学习时长（分钟） */
  totalMinutes: number
  /** 连续打卡天数 */
  streakDays: number
  /** 综合掌握度 0-100 */
  mastery: number
  /** 已点亮的方证节点 */
  litNodes: number
  /** 总答题数（0 = 还没练过，用于空态） */
  answerCount: number
}

export interface RadarItem {
  key: string
  label: string
  /** 0-100 */
  value: number
}

export interface MeShortcuts {
  favorites: number
  notes: number
  wrong: number
}

export interface TimelineItem {
  /** 已格式化：今天 / 昨天 / 10-09 */
  time: string
  text: string
  eventType: string
}

export interface MeDashboard {
  user: UserDto | null
  stats: MeStats
  radar: RadarItem[]
  shortcuts: MeShortcuts
  timeline: TimelineItem[]
}

/** 拉取总览数据（需已登录，token 由 request 拦截器自动带上） */
export function getMeDashboard() {
  return request.get<unknown, MeDashboard>('/biz/me/dashboard')
}

/* ------------------------- 学习档案（/me/profile） ------------------------- */

/** 一部经典的掌握度。mastery 为 0 且 status 为「未开始」时，前端不显示百分比。 */
export interface ClassicItem {
  key: string
  title: string
  /** 0-100，该书答题均分；没有答题记录时为 0 */
  mastery: number
  /** 已练过的目录节点数 */
  practiced: number
  /** 该书可练的目录节点总数 */
  total: number
  answers: number
  /** 已掌握 / 进行中 / 未开始 */
  status: string
}

/** 推荐路径的一步。reason 是后端拼好的中文理由，前端直接展示。 */
export interface PathItem {
  step: number
  nodeId: string
  title: string
  bookTitle: string
  formulaCount: number
  reason: string
}

export interface ProfileSummary {
  answers: number
  litNodes: number
  streakDays: number
  minutes: number
  mastery: number
}

export interface MeProfile {
  radar: RadarItem[]
  classics: ClassicItem[]
  path: PathItem[]
  /** 漏答症状的高频词 */
  weakPoints: string[]
  summary: ProfileSummary
}

/** 学习档案：按经典拆解 + 学习路径 + 薄弱点 */
export function getMeProfile() {
  return request.get<unknown, MeProfile>('/biz/me/profile')
}

/* ------------------------- 收藏夹（/me/favorites） ------------------------- */

export interface FavoriteItem {
  id: number
  /** formula / case / quote */
  targetType: string
  /** 中文类型名，后端给好，前端不翻译 */
  targetLabel: string
  targetId: string
  title: string
  subtitle: string
  /** 可直接跳的路由，如 /formula/f_1 */
  link: string
  /** 今天 / 昨天 / 10-09 */
  createdLabel: string
}

export interface FavoriteList {
  items: FavoriteItem[]
  total: number
}

export function getFavorites() {
  return request.get<unknown, FavoriteList>('/biz/me/favorites')
}

export function addFavorite(targetType: string, targetId: string) {
  return request.post<unknown, FavoriteList>('/biz/me/favorites', { targetType, targetId })
}

export function removeFavorite(id: number) {
  return request.delete<unknown, FavoriteList>(`/biz/me/favorites/${id}`)
}

/* -------------------------- 我的笔记（/me/notes） -------------------------- */

export interface NoteItem {
  id: number
  targetType: string
  targetLabel: string
  targetId: string
  targetTitle: string
  content: string
  link: string
  createdLabel: string
}

export interface NoteList {
  items: NoteItem[]
  total: number
}

export function getNotes() {
  return request.get<unknown, NoteList>('/biz/me/notes')
}

export function saveNote(payload: {
  targetType: string
  targetId: string
  content: string
}) {
  return request.post<unknown, NoteList>('/biz/me/notes', payload)
}

export function removeNote(id: number) {
  return request.delete<unknown, NoteList>(`/biz/me/notes/${id}`)
}

/* --------------------------- 错题本（/me/wrong） --------------------------- */

export interface WrongItem {
  unitRef: string
  nodeTitle: string
  bookTitle: string
  /** 进错题本时那次的分数 */
  lastScore: number
  /** 该单元历史最高分，没答过为 null */
  bestScore: number | null
  attempts: number
  addedLabel: string
}

export interface WrongBook {
  items: WrongItem[]
  summary: { total: number; cleared: number }
}

export function getWrongBook() {
  return request.get<unknown, WrongBook>('/biz/me/wrong')
}

export function removeWrong(unitRef: string) {
  return request.delete<unknown, WrongBook>(`/biz/me/wrong/${unitRef}`)
}

/* ------------------------ 我的方证库（/me/collection） ------------------------ */

export interface FormulaLibItem {
  formulaId: string
  name: string
  nodeTitle: string
  bookTitle: string
  practices: number
  bestScore: number
  lastScore: number
  lastLabel: string
  /** 已掌握 / 待巩固 / 需重练 */
  status: string
}

export interface FormulaLib {
  items: FormulaLibItem[]
  summary: { total: number; mastered: number; learning: number; weak: number }
}

export function getCollection() {
  return request.get<unknown, FormulaLib>('/biz/me/collection')
}

/* --------------------------- 学习路径（/me/path） --------------------------- */

export interface PathStep {
  seq: number
  nodeId: string
  title: string
  bookTitle: string
  formulaCount: number
  score: number | null
  reason: string
  /** done / doing / todo */
  state: string
}

export interface PathPlan {
  practiced: number
  total: number
  percent: number
  done: PathStep[]
  todo: PathStep[]
}

export function getPath() {
  return request.get<unknown, PathPlan>('/biz/me/path')
}
