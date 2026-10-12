<template>
  <div class="crumb"><RouterLink to="/">首页</RouterLink> / 典籍</div>
  <h1 class="serif" style="margin-bottom:6px">典籍浏览</h1>
  <p class="muted" style="margin-bottom:14px">
    按 章 → 节 → 类 → 单元 的层级阅读，仿古籍目录。可切换不同语料（书架）。
  </p>

  <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:18px">
    <span class="pill-tabs">
      <button
        v-for="b in bookTabs"
        :key="b.id"
        :class="{ active: bookId === b.id }"
        :disabled="b.disabled"
        :style="b.disabled ? 'opacity:.5;cursor:not-allowed' : ''"
        @click="switchBook(b)"
      >{{ b.label }}</button>
    </span>
    <RouterLink class="chip clickable" to="/shelf">书架 ↗</RouterLink>
  </div>

  <p v-if="error" class="muted" style="color:#A32D2D">{{ error }}</p>

  <div class="grid" style="grid-template-columns:300px 1fr">
    <!-- 目录树 -->
    <aside class="card" style="align-self:start">
      <h3 style="margin-bottom:12px">
        目录 ·
        <span class="muted" style="font-weight:400;font-size:13px">{{ curBookTitle }}</span>
      </h3>

      <div v-if="loading" class="muted">加载中…</div>

      <template v-else>
        <details v-for="ch in tree" :key="ch.id" open style="margin-bottom:6px">
          <summary style="cursor:pointer;font-weight:700;font-size:14.5px">{{ ch.title }}</summary>
          <details v-for="s in ch.children" :key="s.id" style="margin:6px 0 0 8px">
            <summary style="cursor:pointer;font-size:14px;color:#374151">{{ s.title }}</summary>
            <div
              v-for="c in s.children"
              :key="c.id"
              class="rowitem"
              style="padding:8px 10px;margin-top:6px;cursor:pointer"
              @click="selected = c"
            >{{ c.title }}</div>
          </details>
        </details>
        <p v-if="!tree.length" class="muted">该语料暂无目录数据。</p>
      </template>
    </aside>

    <!-- 内容区 -->
    <section>
      <div class="card">
        <div class="crumb">
          <RouterLink to="/library">典籍</RouterLink> / {{ curBookTitle }}
        </div>
        <h2 class="serif" style="margin-bottom:6px">{{ selected?.title || '—' }}</h2>
        <p class="muted" style="margin-bottom:16px">
          {{ selected ? `该节点下共 ${selected.children.length} 个子单元。` : '请在左侧目录中选择一个节点。' }}
        </p>

        <div v-if="selected && selected.children.length" class="grid cols-2 stagger">
          <a
            v-for="c in selected.children"
            :key="c.id"
            class="rowitem"
            @click="selected = c"
          >
            <span class="thumb">{{ c.title.slice(0, 1) }}</span>
            <div>
              <b>{{ c.title }}</b>
              <div class="muted">{{ c.nodeType }}</div>
            </div>
          </a>
        </div>
        <p v-else class="muted">（叶子节点，后续接入方剂/案例详情）</p>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { getLibraryTree, type BookTreeNode } from '@/api/catalog'
import { toast } from '@/utils/toast'

const bookTabs = [
  { id: 'bk_1', label: '伤寒论', disabled: false },
  { id: 'bk_2', label: '温病学', disabled: false },
  { id: 'bk_3', label: '金匮要略', disabled: false }
]

const bookId = ref('bk_1')
const tree = ref<BookTreeNode[]>([])
const selected = ref<BookTreeNode | null>(null)
const loading = ref(false)
const error = ref('')

const curBookTitle = computed(
  () => bookTabs.find((b) => b.id === bookId.value)?.label ?? bookId.value
)

async function load() {
  loading.value = true
  error.value = ''
  try {
    tree.value = await getLibraryTree(bookId.value)
    selected.value = tree.value[0]?.children?.[0] ?? tree.value[0] ?? null
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载失败'
    tree.value = []
  } finally {
    loading.value = false
  }
}

function switchBook(b: { id: string; label: string; disabled: boolean }) {
  if (b.disabled) return
  bookId.value = b.id
  toast(`已切换到：${b.label}`)
  load()
}

onMounted(load)
</script>
