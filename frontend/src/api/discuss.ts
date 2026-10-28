import request from './request'

/**
 * 讨论区（域2）。
 * 后端：BFF `/api/biz/discuss` → svc-identity `/internal/identity/discuss`。
 *
 * 表是「话题 + 楼层」两级；列表接口一次带回每个话题的前 3 层做预览。
 */

export interface DiscussFloor {
  id: string
  author: string
  content: string
  createdLabel: string
  isPinned: boolean
}

export interface DiscussTopic {
  id: string
  title: string
  targetType: string
  targetId: string
  author: string
  createdLabel: string
  pinned: boolean
  floorCount: number
  floors: DiscussFloor[]
}

export interface DiscussList {
  topics: DiscussTopic[]
  total: number
}

/** 不带参数 = 全部话题；带 targetType/targetId = 某个对象下的讨论 */
export function getDiscuss(params?: { targetType?: string; targetId?: string }) {
  return request.get<unknown, DiscussList>('/biz/discuss', { params: params ?? {} })
}

export function createTopic(payload: {
  targetType: string
  targetId: string
  title: string
  content: string
}) {
  return request.post<unknown, DiscussList>('/biz/discuss', payload)
}

export function replyTopic(topicId: string, content: string) {
  return request.post<unknown, DiscussList>(`/biz/discuss/${topicId}/floor`, { content })
}
