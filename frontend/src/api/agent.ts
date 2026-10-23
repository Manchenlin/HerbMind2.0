import request from './request'

/**
 * 域3 智能域接口（`/api/agent/**`，Agent 服务 :8091）。
 *
 * 现状（对齐 09_API契约清单 §10）：
 *   已实现  GET  /api/agent/health      ✅ 本文件已接
 *   已实现  POST /api/agent/ask/sync    ✅ 本文件已接
 *   未实现  POST /api/agent/ask         SSE 流式（事件 token/tool/citation/done）
 *   未实现  GET  /api/agent/history     会话列表
 *   未实现  POST /api/agent/coach       辨证教练
 *   未实现  POST /api/agent/formula/diff 加减推演
 *   未实现  POST /api/agent/grade       结构化评分
 *
 * 未实现的端点这里**不提供假实现**：调用方拿到 404 就照实提示，
 * 免得前端看起来"能用"、实际是空转。
 */

export interface DepStatus {
  ok: boolean
  detail: string
  latencyMs: number
}

export interface HealthData {
  status: string
  service: string
  version: string
  llm: Record<string, unknown>
  deps: Record<string, DepStatus>
  pgPool: Record<string, unknown>
}

export interface Citation {
  id: string
  refType: string
  refId: string
  title: string
  snippet: string
  score: number
}

export interface AskUsage {
  promptTokens: number
  completionTokens: number
  totalTokens: number
  retrieveMs: number
  llmMs: number
}

export interface AskData {
  answer: string
  citations: Citation[]
  usage: AskUsage
  degraded: boolean
}

/**
 * 开发期身份头。
 * `/api/agent/ask/sync` 强制要求 `X-User-Id`（缺失 401），正式链路由网关注入；
 * 前端直连 8091 调试时必须自己带。这里取登录后写入的 userId，没有就用本地访客 ID，
 * 保证"没登录也能试"，且用户名不会串。
 */
export function currentUserId(): string {
  return localStorage.getItem('userId') || 'u_local_dev'
}

export function getHealth() {
  return request.get<never, HealthData>('/agent/health', {
    headers: { 'X-User-Id': currentUserId() }
  })
}

export function askSync(
  question: string,
  opts: { topK?: number; refType?: 'formula' | 'case'; conversationId?: string } = {}
) {
  return request.post<never, AskData>(
    '/agent/ask/sync',
    {
      question,
      topK: opts.topK,
      refType: opts.refType,
      conversationId: opts.conversationId
    },
    { headers: { 'X-User-Id': currentUserId() }, timeout: 60000 }
  )
}

/** 端点是否尚未实现（404 / 501）——用于把"还没做"和"出错了"分开提示。 */
export function isNotImplemented(e: unknown): boolean {
  const status = (e as { response?: { status?: number } })?.response?.status
  return status === 404 || status === 501 || status === 405
}

/** 把 axios 错误压成一句人话，页面直接显示。 */
export function errMsg(e: unknown, fallback = '请求失败'): string {
  if (e instanceof Error && e.message && !(e as {response?: unknown}).response) return e.message
  const status = (e as { response?: { status?: number } })?.response?.status
  if (status === 401) return '未通过鉴权：请求缺少 X-User-Id（登录后自动带上）'
  if (status === 404) return '接口尚未实现（404）'
  if (status === 500) return '服务端 500：Agent 可能未启动或内部异常，看 :8091 日志'
  if (status === 502 || status === 503) return 'Agent 服务不可达：确认网关 :8080 与 Agent :8091 已启动'
  return fallback
}
