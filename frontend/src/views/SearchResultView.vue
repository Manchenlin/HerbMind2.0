<template>
  <div class="crumb">
    <RouterLink to="/">首页</RouterLink> /
    <RouterLink to="/search">检索</RouterLink> / 结果
  </div>

  <div class="card" style="margin-bottom:18px;display:flex;align-items:center;gap:12px;flex-wrap:wrap">
    <input
      v-model="input"
      class="input"
      style="flex:1;min-width:220px"
      placeholder="试试：“无汗而喘、脉浮紧用什么方” / “桂枝汤的组成”"
      @keyup.enter="submit"
    />
    <button class="btn primary" @click="submit">检索</button>
    <RouterLink class="btn ghost" :to="{ path: '/graph', query: { q: input } }">在图谱中展开</RouterLink>
  </div>

  <div class="grid" style="grid-template-columns:230px 1fr">
    <!-- 分面 -->
    <aside class="card" style="align-self:start">
      <h3 style="margin-bottom:12px">分面统计</h3>

      <div class="muted" style="margin-bottom:8px">类型</div>
      <div style="display:flex;flex-direction:column;gap:6px;font-size:14px">
        <label v-for="t in typeRows" :key="t.key" style="display:flex;gap:8px;align-items:center">
          <input type="checkbox" :checked="type === t.key" @change="toggleType(t.key)" />
          <span>{{ t.label }} ({{ t.count }})</span>
        </label>
      </div>

      <div class="hr"></div>
      <div class="muted" style="margin-bottom:8px">经典</div>
      <div style="display:flex;flex-direction:column;gap:6px;font-size:14px">
        <div v-for="(n, k) in result?.facets.classics || {}" :key="k" class="muted">
          {{ k }} ({{ n }})
        </div>
        <div v-if="!Object.keys(result?.facets.classics || {}).length" class="muted">—</div>
      </div>

      <div class="hr"></div>
      <div class="muted" style="margin-bottom:8px">语料</div>
      <div style="display:flex;flex-direction:column;gap:6px;font-size:14px">
        <div v-for="(n, k) in result?.facets.books || {}" :key="k" class="muted">{{ k }} ({{ n }})</div>
        <div v-if="!Object.keys(result?.facets.books || {}).length" class="muted">—</div>
      </div>

      <div class="hr"></div>
      <div class="muted">
        命中 {{ result?.total ?? 0 }} 条 · 用时 {{ ((result?.tookMs ?? 0) / 1000).toFixed(2) }}s
      </div>
      <div class="muted" style="margin-top:6px;font-size:12px">召回模式：{{ modeLabel }}</div>
    </aside>

    <!-- 结果 -->
    <section>
      <div v-if="loading" class="card"><p class="muted">检索中…</p></div>

      <div v-else-if="error" class="card">
        <h3>检索失败</h3>
        <p class="muted" style="margin-top:6px">{{ error }}</p>
        <p class="muted" style="margin-top:10px">
          请确认 svc-search :8083 与 BFF :8090 已启动。未配置 embedding 服务时仍可做全文/词项召回。
        </p>
      </div>

      <template v-else>
        <div v-if="!result?.list.length" class="card">
          <h3>没有匹配结果</h3>
          <p class="muted" style="margin-top:8px">
            换个说法试试：麻黄汤 / 桂枝 / 无汗 / 脉浮紧；或到
            <RouterLink to="/search" style="color:var(--primary)">检索工作台</RouterLink> 用结构化筛选。
          </p>
        </div>

        <div class="stagger">
          <RouterLink
            v-for="h in result?.list || []"
            :key="h.id"
            class="rowitem"
            :to="linkOf(h)"
            style="margin-bottom:12px"
          >
            <span class="thumb">{{ typeThumb(h.refType) }}</span>
            <div style="flex:1;min-width:0">
              <div style="display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap">
                <b>
                  {{ h.title || '（无标题）' }}
                  <span class="chip primary" style="margin-left:6px">{{ typeLabel(h.refType) }}</span>
                </b>
                <span :class="scoreClass(h.score)">{{ scoreText(h.score) }}</span>
              </div>

              <div
                class="muted"
                style="margin:6px 0;line-height:1.75"
                v-html="highlight(h.snippet, keywords)"
              ></div>

              <div style="display:flex;gap:6px;flex-wrap:wrap;align-items:center">
                <span v-for="hb in h.herbs || []" :key="hb" class="chip">{{ hb }}</span>
                <span v-if="h.page" class="chip">第 {{ h.page }} 页</span>
                <span v-if="h.section" class="chip">{{ h.section }}</span>
                <span v-else-if="h.chapter" class="chip">{{ h.chapter }}</span>
                <span v-for="m in h.matchedBy || []" :key="m" class="chip" style="font-size:11px">
                  {{ legLabel(m) }}
                </span>
              </div>
            </div>
          </RouterLink>
        </div>

        <Pager
          :page="result?.page || 1"
          :total="result?.total || 0"
          :size="result?.size || size"
          @change="goPage"
        />
      </template>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { search, type SearchHit, type SearchResult } from '@/api/search'
import Pager from '@/components/Pager.vue'
import { highlight, scoreClass, scoreText, typeLabel, typeThumb } from '@/utils/format'

const route = useRoute()
const router = useRouter()

const input = ref('')
const result = ref<SearchResult | null>(null)
const loading = ref(false)
const error = ref('')
const size = 10

const q = computed(() => String(route.query.q ?? ''))
const type = computed(() => String(route.query.type ?? 'all'))
const bookId = computed(() => (route.query.bookId ? String(route.query.bookId) : undefined))
const herb = computed(() => (route.query.herb ? String(route.query.herb) : undefined))
const page = computed(() => Number(route.query.page ?? 1) || 1)

const keywords = computed(() => (q.value ? q.value.split(/[\s，。、]+/).filter((x) => x.length >= 2) : []))

const modeLabel = computed(() => {
  switch (result.value?.mode) {
    case 'hybrid':
      return '向量 + 全文混合召回（RRF 融合）'
    case 'fulltext':
      return '中文全文召回（pg_jieba）'
    case 'fuzzy':
      return '词项召回（pg_jieba 未启用时兜底）'
    case 'browse':
      return '全库浏览'
    default:
      return '—'
  }
})

const typeRows = computed(() => {
  const types = result.value?.facets.types ?? {}
  return [
    { key: 'all', label: '全部', count: Object.values(types).reduce((a, b) => a + b, 0) },
    { key: 'formula', label: '方剂', count: types.formula ?? 0 },
    { key: 'case', label: '医案', count: types.case ?? 0 },
    { key: 'quote', label: '条文', count: types.quote ?? 0 }
  ]
})

async function load() {
  if (!q.value) {
    result.value = { list: [], total: 0, page: 1, size, mode: 'browse', tookMs: 0, facets: { types: {}, classics: {}, books: {} } }
    return
  }
  loading.value = true
  error.value = ''
  try {
    result.value = await search(q.value, {
      type: type.value === 'all' ? undefined : type.value,
      bookId: bookId.value,
      herb: herb.value,
      page: page.value,
      size
    })
  } catch (e) {
    error.value = e instanceof Error ? e.message : '检索失败'
    result.value = null
  } finally {
    loading.value = false
  }
}

function submit() {
  router.push({ path: '/search/result', query: { ...route.query, q: input.value, page: 1 } })
}

function toggleType(k: string) {
  router.push({ path: '/search/result', query: { ...route.query, type: k, page: 1 } })
}

function goPage(p: number) {
  router.push({ path: '/search/result', query: { ...route.query, page: p } })
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

function linkOf(h: SearchHit) {
  if (h.refType === 'formula') return `/formula/${h.refId}`
  if (h.refType === 'case') return `/case/${h.refId}`
  const no = (h.title || '').match(/第\s*(\d+)\s*条/)?.[1]
  return no ? `/quote/${h.refId}?no=${no}` : `/quote/${h.refId}`
}

function legLabel(m: string) {
  switch (m) {
    case 'vector':
      return '向量命中'
    case 'fulltext':
      return '全文命中'
    case 'fuzzy':
      return '词项命中'
    case 'quote':
      return '条文命中'
    default:
      return m
  }
}

watch(
  () => route.query,
  () => {
    input.value = q.value
    load()
  },
  { deep: true }
)

onMounted(() => {
  input.value = q.value
  load()
})
</script>
