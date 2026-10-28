<template>
  <div class="crumb"><RouterLink to="/">首页</RouterLink> / 检索</div>

  <h1 class="serif" style="margin-bottom:6px">检索工作台</h1>
  <p class="muted" style="margin-bottom:22px">结构化筛选 + 自然语言语义检索，两种方式任意组合。</p>

  <div class="card" style="margin-bottom:20px">
    <div class="hero-search" style="max-width:none">
      <input
        v-model="q"
        class="input"
        placeholder="无汗而喘、脉浮紧用什么方"
        aria-label="检索词"
        @keyup.enter="onSearch"
      />
      <button class="btn primary" @click="onSearch">检索</button>
    </div>
    <div class="muted" style="margin-top:10px;font-size:13px">
      语义检索：向量召回 bge-m3 ⊕ 中文全文 pg_jieba，混合排序
    </div>
  </div>

  <div class="grid cols-2">
    <!-- 结构化筛选 -->
    <div class="card">
      <h3 style="margin-bottom:6px">结构化筛选</h3>
      <p class="muted" style="margin-bottom:14px">点选维度任意组合。</p>

        <div style="margin-bottom:14px">
        <div class="muted" style="margin-bottom:6px">经典著作</div>
        <p v-if="loadingFacets" class="muted">分面加载中…</p>
        <div v-else-if="!bookOptions.length" class="muted">暂无著作分面数据。</div>
        <div v-else style="display:flex;gap:8px;flex-wrap:wrap">
          <span class="chip clickable" :class="{ sel: !bookId }" @click="bookId = ''">全部</span>
          <span
            v-for="b in bookOptions"
            :key="b.id"
            class="chip clickable"
            :class="{ sel: bookId === b.id }"
            :title="`${b.title}（${b.unitCount ?? 0} 条）`"
            @click="toggleBook(b.id)"
          >{{ b.title }}</span>
        </div>
        <p v-if="facetError" class="muted" style="color:var(--error);margin-top:6px">{{ facetError }}</p>
      </div>

      <div style="margin-bottom:14px">
        <div class="muted" style="margin-bottom:6px">证候 / 症状</div>
        <div style="display:flex;gap:8px;flex-wrap:wrap">
          <span
            v-for="s in SYMPTOMS"
            :key="s"
            class="chip clickable"
            :class="{ sel: symptoms.includes(s) }"
            @click="toggleSymptom(s)"
          >{{ s }}</span>
        </div>
      </div>

      <div style="margin-bottom:14px">
        <div class="muted" style="margin-bottom:6px">药味</div>
        <div style="display:flex;gap:8px;flex-wrap:wrap">
          <span
            v-for="h in HERBS"
            :key="h"
            class="chip clickable"
            :class="{ sel: herb === h }"
            @click="toggleHerb(h)"
          >{{ h }}</span>
        </div>
      </div>

      <div style="margin-bottom:6px">
        <div class="muted" style="margin-bottom:6px">类型</div>
        <div style="display:flex;gap:8px;flex-wrap:wrap">
          <span
            v-for="t in TYPE_OPTIONS"
            :key="t.value"
            class="chip clickable"
            :class="{ sel: typeFilter === t.value }"
            @click="typeFilter = t.value"
          >{{ t.label }}</span>
        </div>
      </div>

      <div class="hr"></div>
      <div style="display:flex;gap:10px">
        <button class="btn primary sm" @click="onApply">应用筛选</button>
        <button class="btn ghost sm" @click="onReset">重置</button>
      </div>
    </div>

    <!-- 其它入口 -->
    <div class="card">
      <h3 style="margin-bottom:14px">其它入口</h3>
      <RouterLink class="rowitem" to="/search/result" style="margin-bottom:10px">
        <span class="thumb">语</span>
        <div>
          <b>自然语言语义检索</b>
          <div class="muted">一句话描述症状，返回最匹配的方证</div>
        </div>
      </RouterLink>
      <RouterLink class="rowitem" to="/search/quote-index" style="margin-bottom:10px">
        <span class="thumb">条</span>
        <div>
          <b>条文反向索引</b>
          <div class="muted">点条文看哪些方/案引用它；点方看相关条文</div>
        </div>
      </RouterLink>
      <RouterLink class="rowitem" to="/graph">
        <span class="thumb">图</span>
        <div>
          <b>在图谱中展开</b>
          <div class="muted">把检索结果映射为知识图谱子图</div>
        </div>
      </RouterLink>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getBooks, type Book } from '@/api/catalog'
import { getFacets, type Facets } from '@/api/search'
import { toast } from '@/utils/toast'

type SearchType = 'all' | 'formula' | 'case' | 'quote'

const SYMPTOMS = ['无汗', '恶风', '脉浮紧', '发热', '项背强']
const HERBS = ['麻黄', '桂枝', '杏仁', '葛根']
const FALLBACK_BOOKS = ['伤寒论', '温病学', '金匮要略']
const TYPE_OPTIONS: Array<{ value: SearchType; label: string }> = [
  { value: 'all', label: '全部' },
  { value: 'formula', label: '方剂' },
  { value: 'case', label: '医案' },
  { value: 'quote', label: '条文' }
]

function queryText(v: unknown): string {
  if (Array.isArray(v)) return String(v[0] ?? '')
  return v === null || v === undefined ? '' : String(v)
}

function isSearchType(v: string): v is SearchType {
  return v === 'all' || v === 'formula' || v === 'case' || v === 'quote'
}

const route = useRoute()
const router = useRouter()

const initialType = queryText(route.query.type)
const q = ref(queryText(route.query.q))
const bookId = ref(queryText(route.query.bookId))
const herb = ref(queryText(route.query.herb))
const typeFilter = ref<SearchType>(isSearchType(initialType) ? initialType : 'all')
const symptoms = ref<string[]>([])

const facets = ref<Facets | null>(null)
const loadingFacets = ref(true)
const facetError = ref('')
const books = ref<Book[]>([])

/** 分面的 key 是书名，但检索参数要的是 bookId（bk_1）——这里用 /catalog/books 做映射 */
const bookOptions = computed<Array<Pick<Book, 'id' | 'title' | 'unitCount'>>>(() => {
  if (books.value.length) {
    return books.value.map((b) => ({ id: b.id, title: b.title, unitCount: b.unitCount }))
  }
  const keys = Object.keys(facets.value?.books ?? {})
  const titles = keys.length ? keys : FALLBACK_BOOKS
  return titles.map((t, i) => ({ id: `bk_${i + 1}`, title: t, unitCount: undefined }))
})

async function loadFacets() {
  loadingFacets.value = true
  facetError.value = ''
  try {
    const [f, b] = await Promise.all([getFacets(''), getBooks().catch(() => [] as Book[])])
    facets.value = f
    books.value = b
  } catch (e) {
    const msg = e instanceof Error ? e.message : '请求失败'
    facetError.value = `分面数据不可用：${msg}（已使用兜底著作列表）`
    facets.value = null
  } finally {
    loadingFacets.value = false
  }
}

function toggleBook(id: string) {
  bookId.value = bookId.value === id ? '' : id
}

function toggleSymptom(name: string) {
  const i = symptoms.value.indexOf(name)
  if (i >= 0) symptoms.value.splice(i, 1)
  else symptoms.value.push(name)
}

function toggleHerb(name: string) {
  herb.value = herb.value === name ? '' : name
}

function resultQuery(withSymptoms: boolean): Record<string, string> | null {
  const parts = withSymptoms ? [...symptoms.value, q.value.trim()] : [q.value.trim()]
  const text = parts.filter((part) => part.length > 0).join(' ')
  if (!text) return null
  const query: Record<string, string> = { q: text }
  if (typeFilter.value !== 'all') query.type = typeFilter.value
  if (bookId.value) query.bookId = bookId.value
  if (herb.value) query.herb = herb.value
  return query
}

function onSearch() {
  if (!q.value.trim()) {
    toast('请输入检索词，例如：无汗而喘、脉浮紧用什么方')
    return
  }
  const query = resultQuery(false)
  if (query) router.push({ path: '/search/result', query })
}

function onApply() {
  const query = resultQuery(true)
  if (!query) {
    toast('请选择筛选条件或输入检索词')
    return
  }
  router.push({ path: '/search/result', query })
}

function onReset() {
  symptoms.value = []
  herb.value = ''
  bookId.value = ''
  typeFilter.value = 'all'
  toast('已重置筛选条件')
}

onMounted(loadFacets)
</script>
