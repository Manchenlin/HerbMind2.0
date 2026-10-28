<template>
  <div class="crumb">
    <RouterLink to="/">首页</RouterLink> / <RouterLink to="/me">我的</RouterLink> / 我的方证库
  </div>
  <h1 class="serif" style="margin-bottom: 6px">我的方证库</h1>
  <p class="muted" style="margin-bottom: 22px">
    按方聚合 —— 一个方练过几次、最好多少分、最近一次怎么样。
  </p>

  <div v-if="loading" class="card"><p class="muted">正在加载方证库…</p></div>
  <div v-else-if="error" class="card">
    <p class="muted" style="color: #a32d2d; margin-bottom: 12px">{{ error }}</p>
    <button class="btn ghost sm" @click="load">重试</button>
  </div>

  <div v-else-if="!data.items.length" class="card center" style="padding: 48px 20px">
    <div style="font-size: 44px">📚</div>
    <p class="muted" style="margin: 12px 0 16px">
      练过的方证会自动进库。现在还是空的，做一道题就有了。
    </p>
    <RouterLink class="btn primary sm" to="/train">去练习</RouterLink>
  </div>

  <template v-else>
    <div class="grid cols-4" style="margin-bottom: 18px">
      <div class="stat"><div class="n">{{ data.summary.total }}</div><div class="l">练过的方</div></div>
      <div class="stat"><div class="n">{{ data.summary.mastered }}</div><div class="l">已掌握（≥80）</div></div>
      <div class="stat"><div class="n">{{ data.summary.learning }}</div><div class="l">待巩固（60-79）</div></div>
      <div class="stat"><div class="n">{{ data.summary.weak }}</div><div class="l">需重练（&lt;60）</div></div>
    </div>

    <div class="pill-tabs" style="margin-bottom: 16px">
      <button
        v-for="t in tabs"
        :key="t"
        :class="{ active: tab === t }"
        @click="tab = t"
      >
        {{ t }}
      </button>
    </div>

    <div class="grid cols-2">
      <div v-for="f in filtered" :key="f.formulaId" class="rowitem">
        <span class="thumb">{{ f.bestScore }}</span>
        <div style="flex: 1; min-width: 0">
          <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap">
            <b>{{ f.name }}</b>
            <span class="chip" :class="chipClass(f.status)" style="font-size: 11px">
              {{ f.status }}
            </span>
          </div>
          <div class="muted">
            {{ f.bookTitle || '—' }} · {{ f.nodeTitle || '—' }}
          </div>
          <div class="muted" style="margin-top: 2px">
            练过 {{ f.practices }} 次 · 最近 {{ f.lastScore }} 分（{{ f.lastLabel }}）
          </div>
        </div>
        <RouterLink
          v-if="f.nodeTitle"
          class="btn ghost sm"
          to="/train"
        >
          再练
        </RouterLink>
      </div>
    </div>

    <p v-if="!filtered.length" class="muted" style="margin-top: 16px">
      这个分类下暂时没有方。
    </p>
  </template>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { getCollection, type FormulaLib } from '@/api/me'

const tabs = ['全部', '已掌握', '待巩固', '需重练'] as const

const data = ref<FormulaLib>({
  items: [],
  summary: { total: 0, mastered: 0, learning: 0, weak: 0 }
})
const loading = ref(true)
const error = ref('')
const tab = ref<string>('全部')

const filtered = computed(() =>
  tab.value === '全部' ? data.value.items : data.value.items.filter((f) => f.status === tab.value)
)

function chipClass(status: string) {
  if (status === '已掌握') return 'primary'
  if (status === '待巩固') return 'gold'
  return 'accent'
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    data.value = await getCollection()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
@media (max-width: 900px) {
  .grid.cols-4 {
    grid-template-columns: repeat(2, 1fr);
  }
  .grid.cols-2 {
    grid-template-columns: 1fr;
  }
}
</style>
