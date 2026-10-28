<template>
  <div class="crumb"><RouterLink to="/">首页</RouterLink> / 书架</div>

  <div style="display:flex;justify-content:space-between;align-items:flex-end;flex-wrap:wrap;gap:12px">
    <div>
      <h1 class="serif" style="margin-bottom:6px">书架 · 语料库</h1>
      <p class="muted">插拔式语料：平台以同一套骨架适配多类书籍，新书接入 = 注册 + 跑导入，不改系统。</p>
    </div>
    <div style="display:flex;gap:10px;flex-wrap:wrap">
      <RouterLink class="btn primary sm" to="/shelf/import">＋ 导入语料</RouterLink>
      <RouterLink class="btn ghost sm" to="/library">进入当前语料 →</RouterLink>
    </div>
  </div>

  <!-- 加载态 -->
  <section v-if="loading" class="card" style="margin-top:22px">
    <p class="muted">书架加载中…</p>
  </section>

  <!-- 请求失败态 -->
  <section v-else-if="error" class="card" style="margin-top:22px">
    <h3>书架加载失败</h3>
    <p class="muted" style="margin-top:6px">{{ error }}</p>
    <p class="muted" style="margin-top:10px">
      请确认后端已启动（BFF :8090 / svc-catalog :8082），且已导入数据快照。
    </p>
    <button class="btn ghost sm" style="margin-top:14px" @click="load">重试</button>
  </section>

  <!-- 空数据态 -->
  <section v-else-if="!books.length" class="card" style="margin-top:22px">
    <h3>书架暂无已接入语料</h3>
    <p class="muted" style="margin-top:6px">
      当前还没有可展示的书籍。可先导入一本，或确认数据快照是否已导入。
    </p>
    <div style="display:flex;gap:10px;margin-top:14px;flex-wrap:wrap">
      <RouterLink class="btn primary sm" to="/shelf/import">＋ 导入语料</RouterLink>
      <button class="btn ghost sm" @click="load">重试</button>
    </div>
  </section>

  <!-- 书架 -->
  <div v-else class="grid cols-3 stagger" style="margin-top:22px">
    <article v-for="(b, i) in books" :key="b.id" class="bookcard" :class="{ dim: !hasUnits(b) }">
      <div class="bookcover" :style="{ background: covers[i % covers.length] }">{{ coverText(b) }}</div>

      <div>
        <div style="display:flex;justify-content:space-between;align-items:center;gap:8px">
          <b>{{ b.title }}</b>
          <span :class="statusInfo(b).chip">{{ statusInfo(b).label }}</span>
        </div>
        <div class="meta" style="margin-top:6px">{{ typeLine(b) }}</div>
        <div class="meta">{{ metaLine(b) }}</div>
      </div>

      <div style="display:flex;justify-content:space-between;align-items:center;gap:8px">
        <span class="meta">
          <span class="status-dot" :style="{ background: statusInfo(b).dot }"></span>
          {{ hasUnits(b) ? `${b.unitCount} 条` : '待接入' }}
        </span>
        <RouterLink
          v-if="hasUnits(b)"
          class="btn primary sm"
          :to="`/library?bookId=${encodeURIComponent(b.id)}`"
        >进入</RouterLink>
        <button v-else class="btn ghost sm" disabled style="opacity:.6;cursor:not-allowed">敬请期待</button>
      </div>
    </article>
  </div>

  <!-- 插拔机制 -->
  <div class="card" style="margin-top:26px">
    <h3 style="margin-bottom:10px">插拔机制</h3>
    <p class="muted">
      ① 注册 <span class="mono">book</span>（书名 / 类型 / 版权 / 状态）→ ② 通用导入器解析为
      <span class="mono">book_node</span> 目录 → ③ 按类型写入特化实体（方证 / 本草 / 药品 / 医案）→
      ④ 登记 <span class="mono">content_unit</span>（向量 + 全文）→ ⑤ 按统一本体建图。
      详见计划文档 14 · 插拔式书籍扩展方案。
    </p>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { getBooks, type Book } from '@/api/catalog'

/** 封面渐变（与 shelf.html 一致，按索引轮换） */
const covers = [
  'linear-gradient(135deg,#2E7D6F,#1F5C52)',
  'linear-gradient(135deg,#3B7DD8,#2A5DA0)',
  'linear-gradient(135deg,#C8A96A,#8A6D3B)',
  'linear-gradient(135deg,#7A6BB5,#5B4E92)',
  'linear-gradient(135deg,#4F8A8B,#376566)'
]

const STATUS_LABEL: Record<string, string> = {
  draft: '待审核',
  已发布: '已发布',
  整理中: '整理中'
}

interface StatusInfo {
  label: string
  chip: string
  dot: string
}

const books = ref<Book[]>([])
const loading = ref(false)
const error = ref('')

function statusInfo(book: Book): StatusInfo {
  const raw = `${book.ingestStatus ?? ''} ${book.statusLabel ?? ''}`
  const label = book.statusLabel || STATUS_LABEL[book.ingestStatus ?? ''] || '规划中'
  if (raw.includes('已发布') || raw.includes('published')) {
    return { label: '已发布', chip: 'chip primary', dot: '#2E9E6B' }
  }
  if (raw.includes('整理') || raw.includes('processing')) {
    return { label: '整理中', chip: 'chip gold', dot: '#D9A441' }
  }
  return { label, chip: 'chip', dot: '#B4B2A9' }
}

function coverText(book: Book): string {
  return book.title.slice(0, 4)
}

function typeLine(book: Book): string {
  return book.bookTypeLabel || book.bookType || '未分类'
}

function metaLine(book: Book): string {
  return `${book.author || '作者未详'} · ${book.dynasty || '朝代未详'}`
}

function hasUnits(book: Book): boolean {
  return (book.unitCount ?? 0) > 0
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    books.value = await getBooks()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载失败'
    books.value = []
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>
