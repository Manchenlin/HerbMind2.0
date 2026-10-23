<template>
  <div class="crumb"><RouterLink to="/">首页</RouterLink> / <RouterLink to="/ask">智能问答</RouterLink> / 会话历史</div>

  <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:14px;flex-wrap:wrap;margin-bottom:14px">
    <div>
      <h1 class="serif" style="font-size:24px">会话历史</h1>
      <p class="muted" style="margin-top:4px">
        共 {{ conversations.length }} 个会话 · 存档在浏览器本地
        （<span class="mono">GET /api/agent/history</span> 未实现，服务端落库后再切过去）
      </p>
    </div>
    <div style="display:flex;gap:8px">
      <button class="btn ghost sm" :disabled="!conversations.length" @click="clearAll">清空全部</button>
      <RouterLink class="btn primary sm" to="/ask">＋ 新会话</RouterLink>
    </div>
  </div>

  <p v-if="!conversations.length" class="muted">还没有会话记录。去<a href="/ask" style="color:var(--primary)">智能问答</a>问一个试试。</p>

  <div v-else class="stagger" style="display:grid;gap:10px">
    <div v-for="c in conversations" :key="c.id" class="rowitem" style="align-items:center">
      <span class="thumb">{{ c.title.slice(0, 1) }}</span>
      <div style="flex:1;min-width:0">
        <div style="font-weight:700">{{ c.title }}</div>
        <div class="muted" style="font-size:12.5px">
          {{ c.messages.length }} 条消息 · 最近 {{ fmt(c.at) }}
          <span v-if="lastQ(c)" style="color:var(--text-3)"> · 首问：{{ lastQ(c) }}</span>
        </div>
      </div>
      <RouterLink class="btn ghost sm" :to="`/ask?c=${c.id}`">继续 →</RouterLink>
      <button class="btn ghost sm" @click="remove(c.id)">删除</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useConversations, type Conversation } from '@/composables/useConversations'
import { toast } from '@/utils/toast'

const { conversations, remove: removeConv, clear } = useConversations()

function fmt(ts: number) {
  const d = new Date(ts)
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

function lastQ(c: Conversation) {
  const first = c.messages.find((m) => m.role === 'me')
  return first ? first.text.slice(0, 24) : ''
}

function remove(id: string) {
  removeConv(id)
  toast('已删除该会话')
}

function clearAll() {
  clear()
  toast('已清空本地会话')
}
</script>
