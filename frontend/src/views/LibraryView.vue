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

  <div class="grid" style="grid-template-columns:300px 1fr">
    <!-- 目录树 -->
    <aside class="card" style="align-self:start;max-height:74vh;overflow:auto">
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

        <NodeDetail v-if="selectedId" :id="selectedId" embedded @open="selectNode" />
        <p v-else class="muted" style="margin-top:12px">请在左侧目录中选择一个节点。</p>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getLibraryTree, type BookTreeNode } from '@/api/catalog'
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
  selectedId.value = id
  // 写进 URL：刷新不丢，也可以把"读到哪一节"的链接发给别人
  router.replace({ query: { ...route.query, bookId: bookId.value, node: id } })
}

function step(delta: number) {
  const target = delta < 0 ? prevNode.value : nextNode.value
  if (target) selectNode(target.id)
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
  bookId.value = b.id
  selectedId.value = ''
  toast(`已切换到：${b.label}`)
  await load()
}

onMounted(async () => {
  await loadBooks()
  if (!bookId.value) bookId.value = defaultBookId.value || 'bk_1'
  await load()
  window.addEventListener('keydown', onKey)
})

onBeforeUnmount(() => window.removeEventListener('keydown', onKey))
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
