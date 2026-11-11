<template>
  <div class="crumb"><RouterLink to="/">首页</RouterLink> / 典籍</div>
  <h1 class="serif" style="margin-bottom:6px">典籍浏览</h1>
  <p class="muted" style="margin-bottom:14px">
    按 章 → 节 → 类 → 单元 的层级阅读，仿古籍目录。点左侧任一节点，右侧就地显示内容，可用 ←/→ 翻页。
  </p>

  <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:18px">
    <span class="pill-tabs">
      <button
        v-for="b in bookTabs"
        :key="b.id"
        :class="{ active: bookId === b.id }"
        @click="switchBook(b)"
      >{{ b.label }}</button>
    </span>
    <RouterLink class="chip clickable" to="/shelf">书架 ↗</RouterLink>
  </div>

  <p v-if="error" class="muted" style="color:#A32D2D">{{ error }}</p>

  <!-- 窄屏下目录树收起，点按钮展开（桌面端这个按钮不显示） -->
  <button class="btn ghost sm toc-toggle" @click="tocOpen = !tocOpen">
    {{ tocOpen ? '收起目录' : '展开目录' }}
  </button>

  <div class="grid lib-layout">
    <!-- 目录树 -->
    <aside class="card lib-toc" :class="{ 'is-open': tocOpen }">
      <h3 style="margin-bottom:12px">
        目录 ·
        <span class="muted" style="font-weight:400;font-size:13px">{{ curBookTitle }}</span>
      </h3>

      <div v-if="loading" class="muted">加载中…</div>

      <template v-else>
        <div v-for="ch in tree" :key="ch.id" class="node-ch">
          <button class="node-btn lvl-1" :class="{ on: isOn(ch.id) }" @click="selectNode(ch.id)">
            {{ ch.title }}
          </button>
          <!-- 章节编号断层时给个占位：第四章第一节「脏腑经络先后病脉证」原文几乎为空，ETL 没建节点，
               直接跳过会让人以为目录错了 -->
          <button v-if="hasGap(ch)" class="node-btn lvl-2 gap" disabled>第一节（原文缺失）</button>
          <div v-for="s in ch.children" :key="s.id">
            <button class="node-btn lvl-2" :class="{ on: isOn(s.id) }" @click="selectNode(s.id)">
              {{ s.title }}
            </button>
            <button
              v-for="c in s.children"
              :key="c.id"
              class="node-btn lvl-3"
              :class="{ on: isOn(c.id) }"
              @click="selectNode(c.id)"
            >{{ c.title }}</button>
          </div>
        </div>
        <p v-if="!tree.length" class="muted">该语料暂无目录数据。</p>
      </template>
    </aside>

    <!-- 内容区：内嵌节点详情 + 上一节 / 下一节 -->
    <section>
      <div class="card">
        <div class="crumb"><RouterLink to="/">首页</RouterLink> / 典籍 / {{ curBookTitle }}</div>

        <div class="lib-nav">
          <button class="btn ghost sm" :disabled="!prevNode" @click="step(-1)">← 上一节</button>
          <span class="muted" style="font-size:12px">{{ posLabel }}</span>
          <button class="btn ghost sm" :disabled="!nextNode" @click="step(1)">下一节 →</button>
          <span style="flex:1"></span>
          <RouterLink v-if="selectedId" class="chip clickable" :to="`/node/${selectedId}`">
            独立页打开 ↗
          </RouterLink>
        </div>

        <!-- 书内搜索：只在本书（可选当前节点子树）范围内召回，点结果直接跳到对应原文 -->
        <div class="lib-search">
          <input
            v-model="q"
            class="lib-search-input"
            placeholder="在本书里搜原文，回车开始"
            @keyup.enter="doSearch"
          />
          <button class="btn ghost sm" :disabled="!q.trim() || searching" @click="doSearch">
            {{ searching ? '搜索中…' : '搜索' }}
          </button>
          <label class="scope">
            <input v-model="scopeCurrent" type="checkbox" />
            只搜当前节点
          </label>
          <button v-if="hits.length" class="btn ghost sm" @click="clearHits">清空结果</button>
        </div>

        <div v-if="hits.length" class="card" style="margin-bottom:14px">
          <p class="muted" style="margin-bottom:8px">
            命中 {{ total }} 条{{ total > hits.length ? `，先显示前 ${hits.length} 条` : '' }}
          </p>
          <a v-for="h in hits" :key="h.id" class="hit" @click="openHit(h)">
            <div class="hit-head">
              <b>{{ hitTitle(h) }}</b>
              <span class="chip" style="font-size:11px">{{ refLabel(h.refType) }}</span>
              <span class="muted hit-meta">
                {{ [h.chapter, h.section, h.page].filter(Boolean).join(' · ') }}
              </span>
            </div>
            <p class="hit-snip">{{ h.snippet || '' }}</p>
          </a>
        </div>

        <!-- 阅读设置：字号与主题只作用于原文区，改完立刻生效并记住 -->
        <div class="reader-bar">
          <span class="muted" style="font-size:12px">字号</span>
          <button class="btn ghost sm" title="缩小" @click="setFont(-1)">A−</button>
          <span style="font-size:12px;min-width:42px;text-align:center">{{ fontSize }}px</span>
          <button class="btn ghost sm" title="放大" @click="setFont(1)">A+</button>
          <span style="flex:1"></span>
          <span class="muted" style="font-size:12px">主题</span>
          <button
            v-for="t in THEMES"
            :key="t.key"
            class="btn ghost sm"
            :class="{ 'is-on': theme === t.key }"
            @click="setTheme(t.key)"
          >{{ t.label }}</button>
        </div>

        <div class="reader-pane" :style="readerStyle">
          <NodeDetail v-if="selectedId" :id="selectedId" embedded @open="selectNode" />
          <p v-else class="muted" style="margin-top:12px">请在左侧目录中选择一个节点。</p>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getLibraryTree, type BookTreeNode } from '@/api/catalog'
import { search, type SearchHit } from '@/api/search'
import NodeDetail from '@/components/NodeDetail.vue'
import { useBooks } from '@/composables/useBooks'
import { toast } from '@/utils/toast'

const router = useRouter()
const route = useRoute()

// tab 由后端书单驱动（composables/useBooks.ts）：合并语料后只有一本，就只显示一个 tab，
// 不会出现硬编码的「伤寒论 / 温病学 / 金匮要略」
const { books, defaultBookId, titleOf, loadBooks } = useBooks()
const bookTabs = computed(() => books.value.map((b) => ({ id: b.id, label: b.title })))

const bookId = ref(String(route.query.bookId ?? ''))
const tree = ref<BookTreeNode[]>([])
const loading = ref(false)
const error = ref('')

const curBookTitle = computed(() => titleOf(bookId.value))

/** 当前节点：用 id 而不是节点对象，方便和 URL 的 ?node= 双向同步 */
const selectedId = ref(String(route.query.node ?? ''))

/** 章 → 节 → 类 展平成阅读顺序，供"上一节 / 下一节"和位置提示使用 */
const flat = computed(() => {
  const list: BookTreeNode[] = []
  for (const chapter of tree.value) {
    list.push(chapter)
    for (const section of chapter.children ?? []) {
      list.push(section)
      for (const category of section.children ?? []) list.push(category)
    }
  }
  return list
})

const idx = computed(() => flat.value.findIndex((n) => n.id === selectedId.value))
const prevNode = computed(() => (idx.value > 0 ? flat.value[idx.value - 1] : null))
const nextNode = computed(() =>
  idx.value >= 0 && idx.value < flat.value.length - 1 ? flat.value[idx.value + 1] : null
)
const posLabel = computed(() =>
  idx.value >= 0 ? `${idx.value + 1} / ${flat.value.length}` : '—'
)

function isOn(id: string) {
  return selectedId.value === id
}

/** 章下第一"节"不是第一节 → 说明前面的节没进库，显示占位而不是静默跳过 */
function hasGap(chapter: BookTreeNode): boolean {
  const first = chapter.children?.[0]
  return !!first && !first.title.startsWith('第一节')
}

function selectNode(id: string) {
  if (!id) return
  saveProgress() // 先记住旧节点读到的位置
  selectedId.value = id
  pendingScroll = 0
  // 写进 URL：刷新不丢，也可以把"读到哪一节"的链接发给别人
  router.replace({ query: { ...route.query, bookId: bookId.value, node: id } })
  window.scrollTo({ top: 0 })
}

/** ===== 阅读进度：记住「上次读到哪一节、滚到哪」 ===== */
const progressKey = (bid: string) => `hm:reading:${bid}`
let pendingScroll = 0
let scrollTimer: number | undefined

interface Progress {
  nodeId: string
  scrollY: number
}

function readProgress(bid: string): Progress | null {
  if (!bid) return null
  try {
    const raw = localStorage.getItem(progressKey(bid))
    if (!raw) return null
    const p = JSON.parse(raw) as Progress
    return p && typeof p.nodeId === 'string' ? p : null
  } catch {
    return null
  }
}

function saveProgress() {
  if (!bookId.value || !selectedId.value) return
  const p: Progress = { nodeId: selectedId.value, scrollY: window.scrollY }
  localStorage.setItem(progressKey(bookId.value), JSON.stringify(p))
}

/** 滚动时低频存一次，避免每次 scroll 都写 localStorage */
function onScroll() {
  if (scrollTimer) return
  scrollTimer = window.setTimeout(() => {
    scrollTimer = undefined
    saveProgress()
  }, 800)
}

/** ===== 字号与主题 ===== */
type ReaderTheme = 'light' | 'sepia' | 'dark'

const FONT_KEY = 'hm:reader:font'
const THEME_KEY = 'hm:reader:theme'

const THEMES: Array<{ key: ReaderTheme; label: string; bg: string; fg: string }> = [
  { key: 'light', label: '日间', bg: '#ffffff', fg: '#333333' },
  { key: 'sepia', label: '泛黄', bg: '#f7efe1', fg: '#3b3125' },
  { key: 'dark', label: '夜间', bg: '#1f2421', fg: '#d9d3c8' }
]

const fontSize = ref(Number(localStorage.getItem(FONT_KEY)) || 15)
const theme = ref<ReaderTheme>((localStorage.getItem(THEME_KEY) as ReaderTheme) || 'light')
const themeCfg = computed(() => THEMES.find((t) => t.key === theme.value) ?? THEMES[0])
const readerStyle = computed(() => ({
  '--reader-font': `${fontSize.value}px`,
  '--reader-bg': themeCfg.value.bg,
  '--reader-fg': themeCfg.value.fg,
  // 夜间模式下原主题绿对比度不足，用浅一档的绿做标题色
  '--reader-accent': theme.value === 'dark' ? '#8fbfa4' : '#2f6a4f',
  background: themeCfg.value.bg,
  color: themeCfg.value.fg
}))

function setFont(delta: number) {
  fontSize.value = Math.min(22, Math.max(13, fontSize.value + delta))
  localStorage.setItem(FONT_KEY, String(fontSize.value))
}

function setTheme(t: ReaderTheme) {
  theme.value = t
  localStorage.setItem(THEME_KEY, t)
}

function step(delta: number) {
  const target = delta < 0 ? prevNode.value : nextNode.value
  if (target) selectNode(target.id)
}

/** ===== 书内搜索 ===== */
const q = ref('')
const hits = ref<SearchHit[]>([])
const total = ref(0)
const searching = ref(false)
/** 默认只搜当前节点子树：读某一节时最常问的是"这一节里有没有提到 X" */
const scopeCurrent = ref(true)

/** 窄屏目录树默认收起（桌面端无关，按钮被 CSS 隐藏） */
const tocOpen = ref(false)

const REF_LABEL: Record<string, string> = { formula: '方剂', case: '医案', node: '原文', quote: '条文' }

function refLabel(t: string): string {
  return REF_LABEL[t] ?? t
}

/** 原文单元的后端 title 可能是书名（其他类型的兜底），优先展示节名 */
function hitTitle(h: SearchHit): string {
  if (h.refType === 'node') return h.section || h.chapter || h.title || '原文'
  return h.title || h.section || h.chapter || '—'
}

async function doSearch() {
  const kw = q.value.trim()
  if (!kw || searching.value) return
  searching.value = true
  error.value = ''
  try {
    const r = await search(kw, {
      bookId: bookId.value,
      nodeId: scopeCurrent.value && selectedId.value ? selectedId.value : undefined,
      size: 20
    })
    hits.value = r.list ?? []
    total.value = r.total ?? hits.value.length
  } catch (e) {
    hits.value = []
    total.value = 0
    error.value = e instanceof Error ? e.message : '搜索失败'
  } finally {
    searching.value = false
  }
}

function clearHits() {
  hits.value = []
  total.value = 0
}

function openHit(h: SearchHit) {
  if (!h.refId) return
  if (h.refType === 'node') {
    selectNode(h.refId)
    window.scrollTo({ top: 0, behavior: 'smooth' })
    return
  }
  if (h.refType === 'formula') void router.push(`/formula/${h.refId}`)
  else if (h.refType === 'case') void router.push(`/case/${h.refId}`)
  else if (h.refType === 'quote') void router.push(`/quote/${h.refId}`)
}

function onKey(e: KeyboardEvent) {
  const el = e.target as HTMLElement | null
  // 正在输入框里打字时不要抢方向键
  if (el && ['INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName)) return
  if (e.key === 'ArrowLeft') step(-1)
  if (e.key === 'ArrowRight') step(1)
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    tree.value = await getLibraryTree(bookId.value)
    // URL 里带的 node 不在这本书里（比如换了语料）→ 退回到第一个节点
    if (!flat.value.some((n) => n.id === selectedId.value)) {
      selectNode(flat.value[0]?.id ?? '')
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载失败'
    tree.value = []
  } finally {
    loading.value = false
  }
}

async function switchBook(b: { id: string; label: string }) {
  if (b.id === bookId.value) return
  saveProgress()
  bookId.value = b.id
  selectedId.value = ''
  toast(`已切换到：${b.label}`)
  restoreProgress()
  await load()
  applyPendingScroll()
}

/** 用上次读到的节点填 selectedId（URL 里已经指定节点时不覆盖） */
function restoreProgress() {
  if (selectedId.value || !bookId.value) return
  const p = readProgress(bookId.value)
  if (p?.nodeId) {
    selectedId.value = p.nodeId
    pendingScroll = p.scrollY ?? 0
  }
}

/**
 * 恢复滚动位置。
 * NodeDetail 的正文是 load() 里异步取的，nextTick 时高度还不够，
 * 所以延后 300ms 再滚一次（本地接口通常 100ms 内返回）。
 */
function applyPendingScroll() {
  if (pendingScroll <= 0) return
  const y = pendingScroll
  pendingScroll = 0
  void nextTick(() => {
    window.scrollTo({ top: y })
    window.setTimeout(() => window.scrollTo({ top: y }), 300)
  })
}

onMounted(async () => {
  await loadBooks()
  if (!bookId.value) bookId.value = defaultBookId.value || 'bk_1'
  restoreProgress()
  await load()
  applyPendingScroll()
  window.addEventListener('keydown', onKey)
  window.addEventListener('scroll', onScroll, { passive: true })
})

onBeforeUnmount(() => {
  saveProgress()
  window.removeEventListener('keydown', onKey)
  window.removeEventListener('scroll', onScroll)
})
</script>

<style scoped>
.lib-nav {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin: 10px 0 16px;
}

.node-ch {
  margin-bottom: 10px;
}

.toc-toggle {
  display: none;
  margin-bottom: 12px;
}

.lib-layout {
  grid-template-columns: 300px 1fr;
}

.lib-toc {
  align-self: start;
  max-height: 74vh;
  overflow: auto;
}

/* 手机/窄平板：目录与内容改成上下排，目录默认收起避免一屏全是目录 */
@media (max-width: 860px) {
  .lib-layout {
    grid-template-columns: 1fr;
  }

  .toc-toggle {
    display: inline-flex;
  }

  .lib-toc {
    display: none;
    max-height: 50vh;
  }

  .lib-toc.is-open {
    display: block;
  }

  .lib-search-input {
    min-width: 0;
  }
}

.reader-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin: 0 0 12px;
}

.reader-bar .is-on {
  border-color: #2f6a4f;
  color: #2f6a4f;
  font-weight: 700;
}

.reader-pane {
  border-radius: 10px;
  padding: 14px 16px;
  transition: background 0.2s ease, color 0.2s ease;
}

.lib-search {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin: 0 0 14px;
}

.lib-search-input {
  flex: 1 1 260px;
  min-width: 200px;
  padding: 8px 12px;
  border: 1px solid var(--border, #e5e7eb);
  border-radius: 8px;
  font: inherit;
  color: inherit;
  background: #fff;
}

.scope {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #6b7280;
}

.hit {
  display: block;
  padding: 10px 0;
  border-top: 1px solid rgba(0, 0, 0, 0.06);
  color: inherit;
  text-decoration: none;
  cursor: pointer;
}

.hit:first-of-type {
  border-top: 0;
}

.hit:hover {
  background: rgba(47, 106, 79, 0.04);
}

.hit-head {
  display: flex;
  align-items: baseline;
  gap: 8px;
  flex-wrap: wrap;
}

.hit-meta {
  font-size: 12px;
}

.hit-snip {
  margin: 6px 0 0;
  font-size: 13px;
  line-height: 1.6;
  color: #4b5563;
}

.node-btn {
  display: block;
  width: 100%;
  text-align: left;
  border: 0;
  background: transparent;
  cursor: pointer;
  border-radius: 6px;
  line-height: 1.45;
  color: inherit;
  font: inherit;
}

.node-btn:hover {
  background: rgba(0, 0, 0, 0.045);
}

.node-btn.on {
  background: rgba(47, 106, 79, 0.12);
  color: #2f6a4f;
  font-weight: 700;
}

.lvl-1 {
  font-weight: 700;
  font-size: 14.5px;
  padding: 5px 6px;
}

.lvl-2 {
  font-size: 13.5px;
  padding: 4px 6px 4px 16px;
  color: #374151;
}

.lvl-3 {
  font-size: 13px;
  padding: 4px 6px 4px 28px;
  color: #6b7280;
}

.gap {
  opacity: 0.5;
  cursor: default;
  font-style: italic;
}

.gap:hover {
  background: transparent;
}
</style>
