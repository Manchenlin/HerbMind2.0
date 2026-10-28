<template>
  <div>
    <!-- 加载态 -->
    <section v-if="loading" class="card">
      <p class="muted">首页加载中…</p>
    </section>

    <!-- 请求失败态 -->
    <section v-else-if="error" class="card">
      <h3>首页加载失败</h3>
      <p class="muted" style="margin-top:6px">{{ error }}</p>
      <p class="muted" style="margin-top:10px">
        请确认后端已启动（BFF :8090 / svc-catalog :8082），且已导入数据快照。
      </p>
      <button class="btn ghost sm" style="margin-top:14px" @click="load">重试</button>
    </section>

    <!-- 空数据态 -->
    <section v-else-if="!home" class="card">
      <h3>暂无首页数据</h3>
      <p class="muted" style="margin-top:6px">
        后端已响应，但没有返回可展示的首页内容。请先导入语料，或稍后重试。
      </p>
      <div style="display:flex;gap:10px;margin-top:14px;flex-wrap:wrap">
        <RouterLink class="btn primary sm" to="/shelf/import">导入语料</RouterLink>
        <button class="btn ghost sm" @click="load">重试</button>
      </div>
    </section>

    <template v-else>
      <p v-if="degraded.length" class="muted" style="margin-bottom:12px">
        ⚠ 部分服务暂不可用：{{ degraded.join('、') }}
      </p>

      <p v-if="isEmpty" class="muted" style="margin-bottom:12px">
        尚未接入语料：可先前往
        <RouterLink to="/shelf/import" style="color:var(--primary)">导入语料</RouterLink>，
        导入后统计、今日方证与图谱会自动出现。
      </p>

      <!-- Hero -->
      <section class="hero">
        <h1>一图见方证，一问解经义，一练成明医。</h1>
        <p>
          一个可插拔的多语料中医知识平台（首个语料《中医经典方证案例研究》，已接入《伤寒论》原文），
          由 AI Agent 驱动，做经方检索 · 临床思维练习 · 科研挖掘。
          <span class="slogan">让方证知识可查、可练、可问、可推演、可看见。</span>
        </p>
        <form class="hero-search" @submit.prevent="goSearch()">
          <input
            v-model="keyword"
            class="input"
            placeholder="试试：“无汗而喘、脉浮紧用什么方” / “桂枝汤的组成”"
            aria-label="语义检索"
          >
          <button class="btn primary" type="submit">智能检索</button>
        </form>
        <div v-if="hotKeywords.length" style="display:flex;gap:10px;margin-top:16px;flex-wrap:wrap">
          <button
            v-for="k in hotKeywords"
            :key="k"
            type="button"
            class="chip clickable"
            @click="goSearch(k)"
          >{{ k }}</button>
        </div>
      </section>

      <!-- 统计条 -->
      <section class="grid cols-4 stagger" style="margin-top:22px">
        <div class="stat">
          <div class="n">{{ num(stats?.vectors ?? stats?.nodes) }}</div>
          <div class="l">结构化内容单元（含向量）</div>
        </div>
        <div class="stat">
          <div class="n">{{ num(stats?.formulas) }}</div>
          <div class="l">方剂</div>
        </div>
        <div class="stat">
          <div class="n">{{ num(stats?.cases) }}</div>
          <div class="l">医案</div>
        </div>
        <div class="stat">
          <div class="n">{{ num(stats?.books) }}</div>
          <div class="l">已接入语料（可扩展）</div>
        </div>
      </section>

      <!-- 语料库（插拔式） -->
      <section class="card" style="margin-top:22px;display:flex;align-items:center;gap:16px;flex-wrap:wrap">
        <div>
          <b>语料库（插拔式）</b>
          <div class="muted">同一套骨架适配多类书籍 · 已接入 {{ books.length }} 部，可扩展</div>
        </div>
        <div v-if="books.length" style="display:flex;gap:8px;flex-wrap:wrap">
          <span v-for="b in books" :key="b.id" :class="bookChipClass(b)">{{ bookChipText(b) }}</span>
        </div>
        <span v-else class="muted">暂无已接入语料</span>
        <RouterLink class="btn ghost sm" style="margin-left:auto" to="/shelf">进入书架 →</RouterLink>
      </section>

      <!-- 今日方证 + 图谱预览 -->
      <section class="grid cols-2" style="margin-top:26px">
        <div class="card">
          <div style="display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap">
            <h3>今日方证<template v-if="today"> · {{ today.name }}</template></h3>
            <span v-if="today?.nodeTitle" class="chip primary">{{ today.nodeTitle }}</span>
          </div>

          <template v-if="today">
            <p class="muted" style="margin:8px 0 14px">
              {{ today.efficacy || '功效未收录' }}。主治：{{ today.syndrome || '证候未收录' }}。
            </p>
            <div style="margin-bottom:14px">
              <HerbChips :herbs="today.herbs" />
            </div>

            <RouterLink
              v-if="firstQuote"
              class="cite"
              :to="`/quote/${firstQuote.id}`"
              style="margin-bottom:16px;display:flex"
            >
              <div>
                <div>{{ firstQuote.content || firstQuote.plainText || '原文未收录' }}</div>
                <div class="pg">
                  {{ firstQuote.label || firstQuote.classicName || '原典' }}<template v-if="firstQuote.articleNo"> · 第 {{ firstQuote.articleNo }} 条</template><template v-if="firstQuote.page"> · 第 {{ firstQuote.page }} 页</template>
                </div>
              </div>
            </RouterLink>
            <p v-else class="muted" style="margin-bottom:16px">暂无原文引用。</p>

            <div style="display:flex;gap:10px;flex-wrap:wrap">
              <RouterLink class="btn primary sm" :to="`/formula/${today.id}`">查看方剂详情</RouterLink>
              <RouterLink class="btn ghost sm" to="/train">开始练习</RouterLink>
            </div>
          </template>

          <p v-else class="muted" style="margin-top:8px">今日方证暂不可用</p>
        </div>

        <div class="card">
          <div style="display:flex;justify-content:space-between;align-items:center;gap:10px">
            <h3>知识图谱 · 预览</h3>
            <RouterLink class="chip clickable" to="/graph">进入图谱 ↗</RouterLink>
          </div>
          <MiniGraph :graph="graph" :w="480" :h="300" />
          <p class="muted">方-药-证 关系网络，可逐层展开、多跳探索。</p>
        </div>
      </section>

      <!-- 大家都在查（A4：catalog + search 聚合） -->
      <template v-if="hotHits.length">
        <h2 class="section-title"><span class="dot"></span>大家都在查</h2>
        <section class="grid cols-4 stagger">
          <RouterLink
            v-for="h in hotHits"
            :key="h.id"
            class="rowitem"
            :to="hitLink(h)"
            style="align-items:flex-start"
          >
            <span class="thumb">{{ typeThumb(h.refType) }}</span>
            <div style="min-width:0">
              <b style="display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">
                {{ h.title || '（无标题）' }}
              </b>
              <div class="muted" style="font-size:12.5px;margin-top:2px">
                {{ typeLabel(h.refType) }} · 相关度 {{ h.score.toFixed(2) }}
              </div>
            </div>
          </RouterLink>
        </section>
      </template>

      <!-- 核心功能 -->
      <h2 class="section-title"><span class="dot"></span>核心功能</h2>
      <section class="grid cols-4 stagger">
        <RouterLink class="card link" to="/search">
          <h3>多维检索</h3>
          <p class="muted">方名 / 证候 / 症状 / 药味 / 条文多维组合，支持自然语言语义检索。</p>
        </RouterLink>
        <RouterLink class="card link" to="/train">
          <h3>先思后看练习</h3>
          <p class="muted">看案例先辨证处方，AI 自动评分，逐条点评，错题自动归集。</p>
        </RouterLink>
        <RouterLink class="card link" to="/graph">
          <h3>知识图谱</h3>
          <p class="muted">方-证-药-症 可视化探索、方证相似度地图、跨经典对照。</p>
        </RouterLink>
        <RouterLink class="card link" to="/ask">
          <h3>AI 智能问答</h3>
          <p class="muted">多工具 Agent 问答，展示推理轨迹，引用可溯源到原典页码。</p>
        </RouterLink>
      </section>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import type { Book } from '@/api/catalog'
import { getHome, type Home } from '@/api/home'
import type { SearchHit } from '@/api/search'
import HerbChips from '@/components/HerbChips.vue'
import MiniGraph from '@/components/MiniGraph.vue'
import { num, typeLabel, typeThumb } from '@/utils/format'
import { toast } from '@/utils/toast'

const router = useRouter()

const home = ref<Home | null>(null)
const loading = ref(false)
const error = ref('')
const keyword = ref('')

const stats = computed(() => home.value?.stats ?? null)
const books = computed(() => home.value?.books ?? [])
const today = computed(() => home.value?.today ?? null)
const graph = computed(() => home.value?.graph ?? null)
const hotKeywords = computed(() => home.value?.hotKeywords ?? [])
const hotHits = computed<SearchHit[]>(() => home.value?.hotHits ?? [])
const degraded = computed(() => home.value?.degraded ?? [])
const firstQuote = computed(() => today.value?.quotes?.[0] ?? null)
const isEmpty = computed(
  () => !!home.value && (stats.value?.nodes ?? 0) === 0 && !today.value && books.value.length === 0
)

const STATUS_LABEL: Record<string, string> = {
  draft: '待审核',
  已发布: '已发布',
  整理中: '整理中'
}

type BookStatusKind = 'published' | 'processing' | 'other'

function statusKind(book: Book): BookStatusKind {
  const raw = `${book.ingestStatus ?? ''} ${book.statusLabel ?? ''}`
  if (raw.includes('已发布') || raw.includes('published')) return 'published'
  if (raw.includes('整理') || raw.includes('processing')) return 'processing'
  return 'other'
}

function bookChipClass(book: Book): string {
  const kind = statusKind(book)
  if (kind === 'published') return 'chip primary'
  if (kind === 'processing') return 'chip gold'
  return 'chip'
}

function bookChipText(book: Book): string {
  if (statusKind(book) === 'published') return book.title
  const label = book.statusLabel || STATUS_LABEL[book.ingestStatus ?? ''] || '规划中'
  return `${book.title} · ${label}`
}

function hitLink(h: SearchHit): string {
  if (h.refType === 'formula') return `/formula/${h.refId}`
  if (h.refType === 'case') return `/case/${h.refId}`
  const no = (h.title || '').match(/第\s*(\d+)\s*条/)?.[1]
  return no ? `/quote/${h.refId}?no=${no}` : `/quote/${h.refId}`
}

function goSearch(q?: string) {  const text = (q ?? keyword.value).trim()
  if (!text) {
    toast('请输入检索关键词')
    return
  }
  router.push({ path: '/search', query: { q: text } })
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    home.value = await getHome()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载失败'
    home.value = null
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>
