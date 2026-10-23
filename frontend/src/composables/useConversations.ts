import { ref } from 'vue'
import type { AskUsage, Citation } from '@/api/agent'

/**
 * 会话本地存档（localStorage）。
 *
 * 为什么先放本地：`GET /api/agent/history` 还没实现（见 09 契约 §10），
 * 而会话列表又是问答页的刚需。等 Agent 的 `agent_conversation / agent_message`
 * 落库后，把这里换成接口调用即可，页面代码不用动。
 * 明确不做的事：不在服务端没实现时伪造一条"已同步"记录。
 */

export interface ChatMessage {
  role: 'me' | 'ai'
  text: string
  citations?: Citation[]
  usage?: AskUsage
  degraded?: boolean
  error?: boolean
  at: number
}

export interface Conversation {
  id: string
  title: string
  at: number
  messages: ChatMessage[]
}

const KEY = 'herbmind.conversations.v1'
const MAX_CONV = 30

function load(): Conversation[] {
  try {
    const raw = localStorage.getItem(KEY)
    if (!raw) return []
    const data = JSON.parse(raw)
    return Array.isArray(data) ? (data as Conversation[]) : []
  } catch {
    return []
  }
}

/** 模块级单例：问答页与历史页共享同一份状态 */
const conversations = ref<Conversation[]>(load())

function persist() {
  try {
    localStorage.setItem(KEY, JSON.stringify(conversations.value.slice(0, MAX_CONV)))
  } catch {
    /* 隐私模式写不进去就算了，不影响本次会话使用 */
  }
}

export function useConversations() {
  function create(title = '新会话'): Conversation {
    const conv: Conversation = { id: `c_${Date.now()}`, title, at: Date.now(), messages: [] }
    conversations.value = [conv, ...conversations.value]
    persist()
    return conv
  }

  function get(id: string): Conversation | undefined {
    return conversations.value.find((c) => c.id === id)
  }

  function touch(conv: Conversation) {
    conv.at = Date.now()
    // 把最近用过的顶到最前面
    conversations.value = [conv, ...conversations.value.filter((c) => c.id !== conv.id)]
    persist()
  }

  function renameFirst(conv: Conversation, text: string) {
    if (conv.title !== '新会话') return
    conv.title = text.slice(0, 20)
    persist()
  }

  function remove(id: string) {
    conversations.value = conversations.value.filter((c) => c.id !== id)
    persist()
  }

  function clear() {
    conversations.value = []
    persist()
  }

  return { conversations, create, get, touch, renameFirst, remove, clear }
}
