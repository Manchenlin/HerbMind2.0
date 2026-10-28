<template>
  <div class="crumb">
    <RouterLink to="/">首页</RouterLink> /
    <RouterLink to="/search">检索</RouterLink> /
    条文反向索引
  </div>

  <h1 class="serif" style="margin-bottom:6px">条文反向索引</h1>
  <p class="muted" style="margin-bottom:18px">点条文看哪些方/案引用它；点方看相关条文。</p>

  <div class="card" style="margin-bottom:18px">
    <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
      <div class="hero-search" style="max-width:none;flex:1;min-width:260px">
        <input
          v-model="q"
          class="input"
          placeholder="输入关键词，如：麻黄汤 / 脉浮紧 / 桂枝"
          aria-label="条文关键词"
          @keyup.enter="onSearch"
        />
        <button class="btn primary" @click="onSearch">检索</button>
      </div>
      <RouterLink class="btn ghost" to="/search">返回检索</RouterLink>
    </div>
  </div>

  <div v-if="loading" class="card">
    <p class="muted">加载中…</p>
  </div>

  <div v-else-if="error" class="card">
    <h3>条文索引加载失败</h3>
    <p class="muted" style="margin-top:6px">{{ error }}</p>
    <p class="muted" style="margin-top:10px">
      请确认后端已启动（svc-catalog :8082 / BFF :8090），且已导入数据快照。
    </p>
    <button class="btn ghost sm" style="margin-top:12px" @click="load">重试</button>
  </div>

  <template v-else>
    <div v-if="!list.length" class="card">
      <h3>暂无结果</h3>
      <p class="muted" style="margin-top:6px">没有匹配的条文；试试：麻黄汤 / 桂枝 / 脉浮紧</p>
    </div>

    <template v-else>
      <p class="muted" style="margin-bottom:10px">共 {{ total }} 条 · 第 {{ page }} 页</p>

      <div style="display:grid;gap:12px">
        <div
          v-for="item in list"
          :key="`${item.quoteId}-${item.articleNo ?? ''}`"
          class="rowitem"
          style="align-items:flex-start"
        >
          <span class="thumb">{{ item.articleNo || '条' }}</span>
          <div style="flex:1;min-width:0">
            <div
              style="display:flex;justify-content:space-between;align-items:baseline;gap:12px;flex-wrap:wrap"
            >
              <div>
                <span>{{ item.classicName || '经典条文' }}</span>
                <b v-if="item.articleNo" style="margin-left:6px">第 {{ item.articleNo }} 条</b>
              </div>
              <span class="muted">{{ item.page ? `第 ${item.page} 页` : '页码未收录' }}</span>
            </div>

            <div style="margin:6px 0">{{ item.text || '（原文待补录）' }}</div>

            <div style="display:flex;gap:6px;flex-wrap:wrap;align-items:center;margin-top:8px">
              <RouterLink
                v-for="f in item.formulas"
                :key="`f-${f.id}`"
                class="chip clickable"
                :to="`/formula/${f.id}`"
              >方 · {{ f.name }}</RouterLink>
              <RouterLink
                v-for="c in item.cases"
                :key="`c-${c.id}`"
                class="chip clickable"
                :to="`/case/${c.id}`"
              >案 · {{ c.name }}</RouterLink>

              <span v-if="!item.formulas.length && !item.cases.length" class="muted">未关联方剂/医案</span>
              <span v-else-if="!item.formulas.length" class="muted">未关联方剂</span>
              <span v-else-if="!item.cases.length" class="muted">未关联医案</span>

              <RouterLink
                class="chip clickable"
                :to="`/quote/${item.quoteId}`"
                style="margin-left:auto"
              >查看条文 ↗</RouterLink>
            </div>
          </div>
        </div>
      </div>

      <Pager :page="page" :total="total" :size="size" @change="onPageChange" />
    </template>
  </template>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getQuoteIndex, type QuoteIndexItem } from '@/api/search'
import Pager from '@/components/Pager.vue'

const route = useRoute()
const router = useRouter()

const size = 20
const q = ref('')
const page = ref(1)
const bookId = ref('')
const list = ref<QuoteIndexItem[]>([])
const total = ref(0)
const loading = ref(false)
const error = ref('')

function queryText(v: unknown): string {
  if (Array.isArray(v)) return String(v[0] ?? '')
  return v === null || v === undefined ? '' : String(v)
}

function parsePage(v: unknown): number {
  const n = Number(queryText(v))
  return Number.isFinite(n) && n >= 1 ? Math.floor(n) : 1
}

function sameQuery(a: Record<string, string>, b: Record<string, string>): boolean {
  return a.q === b.q && a.page === b.page && (a.bookId ?? '') === (b.bookId ?? '')
}

function routeState(): Record<string, string> {
  const state: Record<string, string> = {
    q: queryText(route.query.q),
    page: String(parsePage(route.query.page))
  }
  const book = queryText(route.query.bookId)
  if (book) state.bookId = book
  return state
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const res = await getQuoteIndex(q.value.trim(), page.value, size, bookId.value || undefined)
    list.value = Array.isArray(res.list) ? res.list : []
    total.value = Number(res.total) || 0
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载失败'
    list.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

async function navigate() {
  const next: Record<string, string> = { q: q.value.trim(), page: String(page.value) }
  if (bookId.value) next.bookId = bookId.value
  if (sameQuery(next, routeState())) {
    await load()
    return
  }
  await router.push({ path: '/search/quote-index', query: next })
}

async function onSearch() {
  page.value = 1
  await navigate()
}

async function onPageChange(p: number) {
  if (p === page.value) return
  page.value = p
  await navigate()
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

watch(
  () => [route.query.q, route.query.page, route.query.bookId],
  () => {
    q.value = queryText(route.query.q)
    page.value = parsePage(route.query.page)
    bookId.value = queryText(route.query.bookId)
    void load()
  },
  { immediate: true }
)
</script>
