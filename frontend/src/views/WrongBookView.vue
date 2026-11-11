<template>
  <div class="crumb">
    <RouterLink to="/">首页</RouterLink> / <RouterLink to="/me">我的</RouterLink> / 错题本
  </div>
  <h1 class="serif" style="margin-bottom: 6px">错题本</h1>
  <p class="muted" style="margin-bottom: 22px">
    低于 60 分的练习单元会自动进来；重新练到 60 分以上后，可以自己移出。
  </p>

  <div v-if="loading" class="card"><p class="muted">正在加载错题…</p></div>
  <div v-else-if="error" class="card">
    <p class="muted" style="color: #a32d2d; margin-bottom: 12px">{{ error }}</p>
    <button class="btn ghost sm" @click="load">重试</button>
  </div>

  <div v-else-if="!data.items.length" class="card center" style="padding: 48px 20px">
    <div style="font-size: 44px">✅</div>
    <p class="muted" style="margin: 12px 0 16px">错题本是空的 —— 要么还没练，要么都练过了。</p>
    <RouterLink class="btn primary sm" to="/train">去练习</RouterLink>
  </div>

  <template v-else>
    <div class="grid cols-3" style="margin-bottom: 20px">
      <div class="stat">
        <div class="n">{{ data.summary.total }}</div>
        <div class="l">错题单元</div>
      </div>
      <div class="stat">
        <div class="n">{{ data.summary.cleared }}</div>
        <div class="l">已重新练回来</div>
      </div>
      <div class="stat">
        <div class="n">{{ Math.round(avgLast) }}</div>
        <div class="l">进本时的平均分</div>
      </div>
    </div>

    <div class="grid" style="gap: 12px">
      <div v-for="w in data.items" :key="w.unitRef" class="rowitem">
        <span class="thumb" :class="{ good: isCleared(w) }">{{ w.lastScore }}</span>
        <div style="flex: 1; min-width: 0">
          <b>{{ w.nodeTitle }}</b>
          <div class="muted">
            {{ w.bookTitle || '—' }} · 练过 {{ w.attempts }} 次 · 最高
            {{ w.bestScore ?? '—' }} 分 · 加入于 {{ w.addedLabel }}
          </div>
          <div v-if="isCleared(w)" style="margin-top: 6px">
            <span class="badge ok">已重新练及格</span>
          </div>
          <div v-else-if="w.lastScore >= 60" style="margin-top: 6px">
            <span class="badge warn">进本时已及格 · 建议重练一次</span>
          </div>
        </div>
        <div style="display: flex; gap: 8px; flex-wrap: wrap; justify-content: flex-end">
          <button class="btn primary sm" :disabled="starting === w.unitRef" @click="practice(w)">
            {{ starting === w.unitRef ? '出题中…' : '再练一次' }}
          </button>
          <button class="btn ghost sm" @click="remove(w.unitRef)">移出</button>
        </div>
      </div>
    </div>

    <p v-if="actionError" class="muted" style="color: #a32d2d; margin-top: 12px">
      {{ actionError }}
    </p>
  </template>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getWrongBook, removeWrong, type WrongBook, type WrongItem } from '@/api/me'
import { startSession } from '@/api/train'

const router = useRouter()

const data = ref<WrongBook>({ items: [], summary: { total: 0, cleared: 0 } })
const loading = ref(true)
const error = ref('')
const actionError = ref('')
const starting = ref('')

const avgLast = computed(() => {
  if (!data.value.items.length) return 0
  return data.value.items.reduce((s, x) => s + x.lastScore, 0) / data.value.items.length
})

/** 与后端口径一致：最高分比进本时高且及格，才算真的练回来了 */
function isCleared(w: WrongItem) {
  return w.bestScore !== null && w.bestScore >= 60 && w.bestScore > w.lastScore
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    data.value = await getWrongBook()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

async function practice(w: WrongItem) {
  if (starting.value) return
  starting.value = w.unitRef
  actionError.value = ''
  try {
    const q = await startSession(w.unitRef, '先思后看')
    sessionStorage.setItem('hm_question', JSON.stringify(q))
    router.push(`/train/session/${q.sessionId}`)
  } catch (e) {
    actionError.value = e instanceof Error ? e.message : '出题失败，请稍后重试'
  } finally {
    starting.value = ''
  }
}

async function remove(unitRef: string) {
  actionError.value = ''
  try {
    data.value = await removeWrong(unitRef)
  } catch (e) {
    actionError.value = e instanceof Error ? e.message : '移出失败，请稍后重试'
  }
}

onMounted(load)
</script>

<style scoped>
.rowitem .thumb.good {
  background: var(--success-soft);
  color: #1e7a50;
}

@media (max-width: 900px) {
  .grid.cols-3 {
    grid-template-columns: 1fr;
  }
}
</style>
