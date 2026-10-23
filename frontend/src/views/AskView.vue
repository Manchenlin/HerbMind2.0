<template>
  <div class="crumb"><RouterLink to="/">首页</RouterLink> / 智能问答</div>

  <h1 class="serif" style="font-size:24px;margin-bottom:6px">
    AI 智能问答
    <span class="chip primary" style="font-size:12px;vertical-align:middle">LangChain · 带引用</span>
  </h1>
  <p class="muted" style="margin-bottom:16px">
    走 <span class="mono">POST /api/agent/ask/sync</span>（同步）：pgvector 检索
    <span class="mono">content_unit</span> → 大模型作答 → 返回引用。
    <b>流式 <span class="mono">/api/agent/ask</span>（SSE）尚未实现</b>，所以逐字效果是前端本地呈现，答案与引用都是真实接口返回。
  </p>

  <div class="grid chat-grid">
    <!-- 会话列表 -->
    <aside class="card" style="align-self:start">
      <button class="btn primary sm" style="width:100%" @click="newConv">＋ 新会话</button>
      <div style="margin-top:12px;display:grid;gap:6px;font-size:13.5px">
        <div
          v-for="c in conversations"
          :key="c.id"
          class="rowitem conv"
          :class="{ on: c.id === activeId }"
          @click="switchTo(c.id)"
        >
          <div style="flex:1;min-width:0">
            <div class="conv-title">{{ c.title }}</div>
            <div class="muted" style="font-size:11.5px">{{ c.messages.length }} 条 · {{ fmtTime(c.at) }}</div>
          </div>
        </div>
        <p v-if="!conversations.length" class="muted">还没有会话。</p>
      </div>
      <RouterLink class="chip clickable" to="/ask/history" style="margin-top:12px">全部历史 →</RouterLink>
    </aside>

    <!-- 对话 -->
    <section class="card" style="padding:0;display:flex;flex-direction:column">
      <div class="chatbox">
        <template v-for="(m, i) in messages" :key="i">
          <div v-if="m.role === 'me'" class="bubble me">{{ m.text }}</div>

          <div v-else>
            <!-- 处理轨迹：真实耗时/token，不是编的工具事件 -->
            <details v-if="m.usage && !m.error" class="toolcard">
              <summary>
                检索与生成 · 检索 {{ m.usage.retrieveMs }}ms / 生成 {{ m.usage.llmMs }}ms
                <span class="muted">（同步接口一次返回，非流式）</span>
              </summary>
              <div class="toolstep">
                <span class="k">retrieve</span>
                <span class="muted">
                  pgvector 相似度检索 → 命中 {{ m.citations?.length ?? 0 }} 条资料，耗时 {{ m.usage.retrieveMs }}ms
                </span>
              </div>
              <div class="toolstep">
                <span class="k">llm</span>
                <span class="muted">
                  生成耗时 {{ m.usage.llmMs }}ms · tokens {{ m.usage.promptTokens }} → {{ m.usage.completionTokens }}（共 {{ m.usage.totalTokens }}）
                </span>
              </div>
            </details>

            <div
              class="bubble ai"
              :class="{ typing: isTyping(i) }"
              :style="m.error ? 'border-color:#E7BDB8;background:#FAF3F2' : ''"
            >{{ displayText(m, i) }}</div>

            <div v-if="m.degraded" class="chip warn" style="margin-top:8px">
              降级回答（degraded=true）：资料不足或模型不可用，未经大模型生成
            </div>

            <div v-if="m.citations?.length && !isTyping(i)" style="margin-top:12px">
              <div v-for="c in m.citations" :key="c.id" class="cite" style="margin-bottom:8px">
                <div>
                  <div class="snip">{{ c.snippet }}</div>
                  <div class="pg">
                    {{ c.title || c.refId }} · {{ c.refType === 'formula' ? '方剂' : '医案' }} ·
                    相似度 {{ (c.score * 100).toFixed(0) }}% ·
                    <RouterLink :to="srcLink(c)">看原文 ↗</RouterLink>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </template>

        <div v-if="loading" class="bubble ai" style="display:flex;align-items:center;gap:10px">
          <span class="spin"></span>
          <span class="muted">正在检索资料并生成回答…</span>
        </div>

        <p v-if="!messages.length && !loading" class="muted">
          问点什么试试，例如「无汗而喘、脉浮紧用什么方？」
        </p>
      </div>

      <div class="inputbar">
        <input
          ref="inputEl"
          v-model="draft"
          class="input"
          placeholder="继续追问，例如：“为什么不用桂枝汤？”（Enter 发送）"
          :disabled="loading"
          @keyup.enter="send"
        />
        <button class="btn primary" :disabled="loading || !draft.trim()" @click="send">发送</button>
      </div>
    </section>

    <!-- 右侧联动 -->
    <aside style="display:grid;gap:16px;align-self:start">
      <div class="card">
        <h3 style="font-size:15px;margin-bottom:10px">相关方证</h3>
        <RouterLink
          v-for="f in relatedFormulas"
          :key="f.refId"
          class="rowitem"
          style="padding:10px;margin-bottom:8px"
          :to="`/formula/${f.refId}`"
        >
          <span class="thumb" style="width:36px;height:36px;font-size:13px">{{ f.title.slice(0, 1) }}</span>
          <div>
            <b>{{ f.title }}</b>
            <div class="muted">相似度 {{ (f.score * 100).toFixed(0) }}%</div>
          </div>
        </RouterLink>
        <p v-if="!relatedFormulas.length" class="muted" style="font-size:13px">
          提问后，这里会列出本次回答引用的方剂。
        </p>
      </div>

      <div class="card">
        <h3 style="font-size:15px;margin-bottom:8px">联动图谱</h3>
        <svg v-if="mini.nodes.length" viewBox="0 0 260 150" style="width:100%">
          <line
            v-for="(e, i) in mini.edges"
            :key="`l-${i}`"
            :x1="e.a.x"
            :y1="e.a.y"
            :x2="e.b.x"
            :y2="e.b.y"
            stroke="#C9CFC9"
            stroke-width="1.3"
          />
          <g v-for="n in mini.nodes" :key="n.id">
            <circle
              :cx="n.x"
              :cy="n.y"
              :r="n.main ? 20 : 14"
              :fill="NODE_STYLE[n.label].fill"
              :stroke="NODE_STYLE[n.label].stroke"
              stroke-width="2"
            />
            <text
              :x="n.x"
              :y="n.y + 4"
              text-anchor="middle"
              :font-size="n.main ? 10 : 9"
              :fill="NODE_STYLE[n.label].text"
            >{{ n.short }}</text>
          </g>
        </svg>
        <p v-else class="muted" style="font-size:13px">
          引用命中示意图中的方剂后，这里会展示它的邻居小图。
        </p>
        <p v-if="mini.nodes.length" class="muted" style="font-size:11.5px;margin-top:6px">
          示意数据 · 待 <span class="mono">/api/agent/graph/**</span>
        </p>
      </div>

      <div class="card">
        <h3 style="font-size:15px;margin-bottom:6px">跟诊剧本杀</h3>
        <p class="muted" style="font-size:13px">让 Agent 扮患者多轮陈述，你来辨证处方。</p>
        <button class="btn ghost sm" style="margin-top:10px" @click="coach">开始一局</button>
        <p class="muted" style="font-size:11.5px;margin-top:6px">
          <span class="mono">POST /api/agent/coach</span> 未实现
        </p>
      </div>
    </aside>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { askSync, errMsg, type Citation } from '@/api/agent'
import { useConversations, type ChatMessage } from '@/composables/useConversations'
import { NODE_STYLE, neighborSubgraph, resolveNodeId, type GNode } from '@/mock/domain3'
import { toast } from '@/utils/toast'

const route = useRoute()
const { conversations, create, get, touch, renameFirst } = useConversations()

const activeId = ref('')
const draft = ref('')
const loading = ref(false)
const inputEl = ref<HTMLInputElement | null>(null)

const activeConv = computed(() => conversations.value.find((c) => c.id === activeId.value) ?? null)
const messages = computed<ChatMessage[]>(() => activeConv.value?.messages ?? [])

/* ---------------- 会话切换 ---------------- */
function newConv() {
  const c = create()
  activeId.value = c.id
  draft.value = ''
  nextTick(() => inputEl.value?.focus())
}

function switchTo(id: string) {
  activeId.value = id
}

function ensureConv() {
  if (activeConv.value) return activeConv.value
  const c = create()
  activeId.value = c.id
  return c
}

/* ---------------- 打字机（本地呈现，非 SSE） ---------------- */
const typingIndex = ref(-1)
const typingShown = ref(0)
let timer: number | null = null

function stopTyping() {
  if (timer !== null) {
    window.clearInterval(timer)
    timer = null
  }
  typingIndex.value = -1
}

function startTyping(idx: number) {
  stopTyping()
  const full = messages.value[idx]?.text.length ?? 0
  typingIndex.value = idx
  typingShown.value = 0
  timer = window.setInterval(() => {
    typingShown.value = Math.min(full, typingShown.value + 3)
    if (typingShown.value >= full) stopTyping()
  }, 22)
}

function isTyping(i: number) {
  return typingIndex.value === i && typingShown.value < (messages.value[i]?.text.length ?? 0)
}

function displayText(m: ChatMessage, i: number) {
  if (i === typingIndex.value) return m.text.slice(0, typingShown.value)
  return m.text
}

/* ---------------- 发送 ---------------- */
async function send() {
  const q = draft.value.trim()
  if (!q || loading.value) return

  const conv = ensureConv()
  conv.messages.push({ role: 'me', text: q, at: Date.now() })
  renameFirst(conv, q)
  draft.value = ''
  loading.value = true

  try {
    const data = await askSync(q, { conversationId: conv.id })
    conv.messages.push({
      role: 'ai',
      text: data.answer,
      citations: data.citations,
      usage: data.usage,
      degraded: data.degraded,
      at: Date.now()
    })
    touch(conv)
    await nextTick()
    startTyping(conv.messages.length - 1)
  } catch (e) {
    conv.messages.push({
      role: 'ai',
      text: `请求失败：${errMsg(e, '无法获取回答')}`,
      error: true,
      at: Date.now()
    })
    touch(conv)
  } finally {
    loading.value = false
  }
}

/* ---------------- 右侧联动 ---------------- */
const lastCitations = computed<Citation[]>(() => {
  for (let i = messages.value.length - 1; i >= 0; i--) {
    const m = messages.value[i]
    if (m.role === 'ai' && m.citations?.length) return m.citations
  }
  return []
})

const relatedFormulas = computed(() => {
  const seen = new Set<string>()
  return lastCitations.value
    .filter((c) => c.refType === 'formula' && c.title)
    .filter((c) => (seen.has(c.refId) ? false : (seen.add(c.refId), true)))
    .slice(0, 4)
})

/** 小图：取最近一条引用里能对上示意图的方，展开 1 跳邻居（最多 3 个） */
const mini = computed<{ nodes: Array<GNode & { main: boolean; short: string }>; edges: Array<{ a: GNode; b: GNode }> }>(
  () => {
    const first = relatedFormulas.value[0]
    if (!first) return { nodes: [], edges: [] }
    const cid = resolveNodeId(first.title)
    const sub = neighborSubgraph(cid, 1)
    if (!sub.center) return { nodes: [], edges: [] }

    const neighborHoles = [
      { x: 52, y: 34 },
      { x: 208, y: 34 },
      { x: 130, y: 132 }
    ]
    const others = sub.nodes.filter((n) => n.id !== sub.center!.id).slice(0, 3)
    const placed: Array<GNode & { main: boolean; short: string }> = [
      { ...sub.center, x: 130, y: 75, r: 20, main: true, short: short(sub.center.name, 3) }
    ]
    others.forEach((n, i) => {
      placed.push({ ...n, x: neighborHoles[i].x, y: neighborHoles[i].y, r: 14, main: false, short: short(n.name, 2) })
    })
    const byId = new Map(placed.map((n) => [n.id, n]))
    const edges: Array<{ a: GNode; b: GNode }> = []
    for (const e of sub.edges) {
      const a = byId.get(e.from)
      const b = byId.get(e.to)
      if (a && b) edges.push({ a, b })
    }
    return { nodes: placed, edges }
  }
)

function short(name: string, n: number) {
  return name.length > n ? `${name.slice(0, n)}…` : name
}

function srcLink(c: Citation) {
  return c.refType === 'formula' ? `/formula/${c.refId}` : `/case/${c.refId}`
}

function coach() {
  toast('辨证教练 /api/agent/coach 尚未实现，先记这里')
}

function fmtTime(ts: number) {
  const d = new Date(ts)
  return `${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

onMounted(() => {
  const q = route.query.q
  if (typeof q === 'string' && q) draft.value = q

  const cid = route.query.c
  const target = typeof cid === 'string' ? get(cid) : undefined
  if (target) activeId.value = target.id
  else if (conversations.value.length) activeId.value = conversations.value[0].id
  else activeId.value = create().id

  nextTick(() => inputEl.value?.focus())
})

onUnmounted(stopTyping)
</script>

<style scoped>
.chat-grid {
  grid-template-columns: 220px 1fr 300px;
  align-items: start;
}
@media (max-width: 1100px) {
  .chat-grid {
    grid-template-columns: 1fr;
  }
}
.chatbox {
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: 460px;
  max-height: 62vh;
  overflow-y: auto;
}
.inputbar {
  border-top: 1px solid var(--border);
  padding: 14px;
  display: flex;
  gap: 10px;
  align-items: center;
}
/* 按钮被 flex 挤压时中文会竖排换行，固定不收缩 */
.inputbar .btn {
  flex: none;
  white-space: nowrap;
  padding: 11px 22px;
}
.conv {
  padding: 8px 10px;
  cursor: pointer;
}
.conv.on {
  border-color: #cde6df;
  background: var(--primary-soft);
}
.conv-title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 600;
}
.bubble.ai {
  max-width: 100%;
  white-space: pre-wrap;
}
/* 引用原文可能很长，气泡里只看三行，完整内容点「看原文」 */
.snip {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
