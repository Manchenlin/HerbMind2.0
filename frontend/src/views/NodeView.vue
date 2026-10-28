<template>
  <div class="crumb">
    <RouterLink to="/">首页</RouterLink> /
    <RouterLink to="/library">典籍</RouterLink>
    <template v-if="d?.bookTitle"> / {{ d.bookTitle }}</template>
    <template v-if="d">
      <template v-for="b in d.breadcrumb" :key="b.id">
        / <RouterLink :to="`/node/${b.id}`">{{ b.name }}</RouterLink>
      </template>
      / {{ d.node.title }}
    </template>
  </div>

  <div v-if="loading" class="card">
    <p class="muted">加载中…</p>
  </div>

  <div v-else-if="error" class="card">
    <h3>目录节点加载失败</h3>
    <p class="muted" style="margin-top:6px">{{ error }}</p>
    <p class="muted" style="margin-top:10px">
      请确认后端已启动（svc-catalog :8082 / BFF :8090），且已导入数据快照。
    </p>
    <button class="btn ghost sm" style="margin-top:12px" @click="load">重试</button>
  </div>

  <template v-else-if="d">
    <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px;flex-wrap:wrap">
      <div>
        <h1 class="serif" style="font-size:30px">{{ d.node.title }}</h1>
        <p class="muted" style="margin-top:6px">
          该节点下共 {{ d.childCount }} 个直接子节点 · {{ d.formulas.length }} 个方剂 ·
          {{ d.cases.length }} 则医案 · {{ d.quotes.length }} 条相关条文
        </p>
      </div>
      <RouterLink class="chip clickable" to="/library">← 返回典籍</RouterLink>
    </div>

    <template v-if="d.node.children.length">
      <h2 class="section-title"><span class="dot"></span>子节点</h2>
      <div class="grid cols-2 stagger">
        <RouterLink v-for="c in d.node.children" :key="c.id" class="rowitem" :to="`/node/${c.id}`">
          <span class="thumb">{{ c.title.slice(0, 1) || '节' }}</span>
          <div>
            <b>{{ c.title }}</b>
            <div class="muted">{{ nodeTypeLabel(c.nodeType) }}</div>
          </div>
        </RouterLink>
      </div>
    </template>

    <template v-if="d.formulas.length">
      <h2 class="section-title"><span class="dot"></span>本节点方剂</h2>
      <div class="grid cols-2">
        <RouterLink v-for="f in d.formulas" :key="f.id" class="rowitem" :to="`/formula/${f.id}`">
          <span class="thumb">{{ f.name.slice(0, 1) || '方' }}</span>
          <div>
            <b>{{ f.name }}</b>
            <div class="muted">
              {{ f.efficacy || f.syndrome || '证治待补录' }}
              <template v-if="f.page"> · 第 {{ f.page }} 页</template>
            </div>
          </div>
        </RouterLink>
      </div>
    </template>

    <template v-if="d.cases.length">
      <h2 class="section-title"><span class="dot"></span>相关医案</h2>
      <div style="display:grid;gap:10px">
        <RouterLink v-for="c in d.cases" :key="c.id" class="rowitem" :to="`/case/${c.id}`">
          <span class="thumb">案</span>
          <div>
            <b>{{ c.title || '医案' }}</b>
            <div class="muted">
              <template v-if="c.mainFormulaName">{{ c.mainFormulaName }}</template>
              <template v-if="c.mainFormulaName && c.page"> · </template>
              <template v-if="c.page">第 {{ c.page }} 页</template>
              <template v-if="!c.mainFormulaName && !c.page">暂无摘要</template>
            </div>
          </div>
        </RouterLink>
      </div>
    </template>

    <template v-if="d.quotes.length">
      <h2 class="section-title"><span class="dot"></span>经典条文</h2>
      <div style="display:grid;gap:10px">
        <RouterLink
          v-for="q in d.quotes"
          :key="q.id + (q.articleNo ?? '')"
          class="cite"
          :to="`/quote/${q.id}`"
        >
          <div>
            <div>{{ excerpt(q.content || q.plainText) || '（原文待补录）' }}</div>
            <div class="pg">
              {{ q.label || q.classicName || '经典条文' }}
              <template v-if="q.page"> · 第 {{ q.page }} 页</template>
              · 查看条文 ↗
            </div>
          </div>
        </RouterLink>
      </div>
    </template>

    <div v-if="isEmpty" class="card" style="margin-top:18px">
      <p class="muted">该节点暂无内容（可能该分类尚未挂接方剂）</p>
    </div>
  </template>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { getNodeDetail, type NodeDetail } from '@/api/catalog'

const route = useRoute()
const id = computed(() => String(route.params.id))

const d = ref<NodeDetail | null>(null)
const loading = ref(false)
const error = ref('')

const isEmpty = computed(
  () => !!d.value && !d.value.formulas.length && !d.value.cases.length && !d.value.quotes.length
)

const NODE_TYPE_LABEL: Record<string, string> = {
  chapter: '章',
  section: '节',
  category: '类方证'
}

function nodeTypeLabel(nodeType?: string): string {
  if (!nodeType) return '节点'
  return NODE_TYPE_LABEL[nodeType] ?? nodeType
}

function excerpt(text?: string, max = 120): string {
  if (!text) return ''
  return text.length > max ? `${text.slice(0, max)}…` : text
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    d.value = await getNodeDetail(id.value)
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载失败'
    d.value = null
  } finally {
    loading.value = false
  }
}

watch(id, load)
onMounted(load)
</script>
