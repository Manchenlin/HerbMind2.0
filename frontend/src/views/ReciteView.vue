<template>
  <div class="crumb">
    <RouterLink to="/">首页</RouterLink> / <RouterLink to="/train">练习</RouterLink> / 背诵打卡
  </div>
  <h1 class="serif" style="margin-bottom: 6px">背诵打卡</h1>
  <p class="muted" style="margin-bottom: 22px">
    默写条文，按字面比对给分；背对的隔几天再问一次（间隔重复）。
  </p>

  <div v-if="loading" class="card"><p class="muted">正在加载待背条文…</p></div>
  <div v-else-if="error" class="card">
    <p class="muted" style="color: #a32d2d; margin-bottom: 12px">{{ error }}</p>
    <button class="btn ghost sm" @click="load">重试</button>
  </div>

  <template v-else>
    <div class="grid cols-4" style="margin-bottom: 20px">
      <div class="stat"><div class="n">{{ data.stats.total }}</div><div class="l">可背条文</div></div>
      <div class="stat"><div class="n">{{ data.stats.due }}</div><div class="l">今天到期</div></div>
      <div class="stat"><div class="n">{{ data.stats.mastered }}</div><div class="l">已背熟</div></div>
      <div class="stat"><div class="n">{{ data.stats.streak }}</div><div class="l">连续打卡（天）</div></div>
    </div>

    <div v-if="!data.items.length" class="card">
      <p class="muted">条文库里暂时没有可背的条文。</p>
    </div>

    <div v-else class="grid" style="grid-template-columns: 1fr 320px">
      <!-- 当前默写 -->
      <section v-if="current" class="card">
        <div class="head">
          <div>
            <h3 style="margin-bottom: 4px">
              {{ current.classicName }}
              <span v-if="current.articleNo" class="muted" style="font-size: 13px">
                · 第 {{ current.articleNo }} 条
              </span>
            </h3>
            <span class="chip" :class="current.due ? 'accent' : ''">
              {{ current.due ? '今天该复习' : current.lastResult ? '已背过' : '未开始' }}
            </span>
          </div>
          <span class="muted" style="font-size: 12.5px">
            {{ index + 1 }} / {{ data.items.length }}
          </span>
        </div>

        <!-- 默写区：不显示原文，只给起句与字数 -->
        <div v-if="!result" style="margin-top: 16px">
          <div class="hint">
            <div class="muted" style="font-size: 12px; margin-bottom: 4px">起句提示</div>
            <b style="font-size: 15px">{{ current.hint }}</b>
            <span class="muted" style="margin-left: 10px; font-size: 12.5px">
              共 {{ current.charCount }} 字 · 标点不必一致
            </span>
          </div>
          <textarea
            v-model="draft"
            class="input"
            rows="5"
            placeholder="接着往下默写…"
            style="margin-top: 12px"
          />
          <div style="display: flex; gap: 10px; margin-top: 12px; flex-wrap: wrap">
            <button class="btn primary" :disabled="submitting" @click="submit">
              {{ submitting ? '判分中…' : '提交默写' }}
            </button>
            <button class="btn ghost" @click="next">换一条</button>
          </div>
          <p v-if="submitError" class="muted" style="color: #a32d2d; margin-top: 10px">
            {{ submitError }}
          </p>
        </div>

        <!-- 判分结果 -->
        <div v-else style="margin-top: 16px">
          <div class="score-head">
            <div class="score-num">{{ result.score }}</div>
            <div>
              <h3 style="margin-bottom: 2px">{{ result.level }}</h3>
              <div class="muted" style="font-size: 13px">
                下次复习：{{ result.nextReviewLabel }}
                <template v-if="result.mastered"> · 已算背熟</template>
              </div>
            </div>
          </div>

          <div style="margin-bottom: 14px">
            <div class="muted dlabel">漏掉的分句</div>
            <div class="chips">
              <span v-for="m in result.missed" :key="m" class="chip accent">{{ m }}</span>
              <span v-if="!result.missed.length" class="muted" style="font-size: 13px">
                一个不差
              </span>
            </div>
          </div>

          <div class="cite" style="margin-bottom: 14px">
            <div>
              <div><b>原文：</b>{{ result.standard }}</div>
              <div v-if="answered?.plainText" class="pg">{{ answered.plainText }}</div>
              <div class="pg">字面比对 · 不做语义改写判定</div>
            </div>
          </div>

          <div style="display: flex; gap: 10px; flex-wrap: wrap">
            <button class="btn primary" @click="next">下一条</button>
            <button class="btn ghost" @click="again">再背一次</button>
          </div>
        </div>
      </section>

      <!-- 待背列表 -->
      <aside class="card" style="align-self: start">
        <h3 style="margin-bottom: 12px">待背 · 到期优先</h3>
        <div class="list">
          <button
            v-for="(it, i) in data.items"
            :key="it.quoteId"
            class="item"
            :class="{ active: i === index }"
            @click="pick(i)"
          >
            <span class="dot" :class="it.due ? 'due' : ''"></span>
            <span style="flex: 1; text-align: left">
              <b style="font-size: 13.5px">{{ it.hint }}</b>
              <span class="muted" style="display: block; font-size: 12px">
                {{ it.classicName }}
                <template v-if="it.articleNo"> · {{ it.articleNo }}</template>
                · {{ it.charCount }} 字
              </span>
              <span class="muted" style="display: block; font-size: 12px">
                {{ it.lastResult ? `上次：${it.lastResult}` : '未背过' }}
                <template v-if="it.reviewLabel"> · 下次 {{ it.reviewLabel }}</template>
              </span>
            </span>
          </button>
        </div>
      </aside>
    </div>
  </template>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  getRecite,
  submitRecite,
  type ReciteData,
  type ReciteItem,
  type ReciteResult
} from '@/api/train'

const data = ref<ReciteData>({
  items: [],
  stats: { total: 0, due: 0, mastered: 0, streak: 0 }
})
const loading = ref(true)
const error = ref('')

const index = ref(0)
const draft = ref('')
const submitting = ref(false)
const submitError = ref('')
const result = ref<ReciteResult | null>(null)
/**
 * 刚判完的那一条。
 * 判分后列表会重新排序（背完就从「到期」移走），index 指向的可能已经不是同一条了，
 * 所以结果卡片必须绑在快照上，而不是绑在 current 上。
 */
const answered = ref<ReciteItem | null>(null)

const current = computed(() => data.value.items[index.value] ?? null)

async function load() {
  loading.value = true
  error.value = ''
  try {
    data.value = await getRecite()
    index.value = 0
    resetAnswer()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

function resetAnswer() {
  draft.value = ''
  result.value = null
  answered.value = null
  submitError.value = ''
}

function pick(i: number) {
  index.value = i
  resetAnswer()
}

function next() {
  if (!data.value.items.length) return
  index.value = (index.value + 1) % data.value.items.length
  resetAnswer()
}

/** 再背一次：定位回刚背的那条，清空结果重写（列表已重排，所以要按 quoteId 找） */
function again() {
  const target = answered.value
  const at = target ? data.value.items.findIndex((t) => t.quoteId === target.quoteId) : -1
  if (at >= 0) index.value = at
  result.value = null
  draft.value = ''
}

async function submit() {
  const q = current.value
  if (!q || submitting.value) return
  if (!draft.value.trim()) {
    submitError.value = '先把记得的写下来，哪怕只写半句'
    return
  }
  submitting.value = true
  submitError.value = ''
  try {
    answered.value = q
    result.value = await submitRecite({ quoteId: q.quoteId, text: draft.value.trim() })
    // 判完分刷新统计（到期数、已背熟、打卡天数都会变）
    data.value = await getRecite()
  } catch (e) {
    submitError.value = e instanceof Error ? e.message : '判分失败，请稍后重试'
  } finally {
    submitting.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}

.score-head {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 16px;
}

.hint {
  background: var(--surface-2);
  border-radius: var(--radius);
  padding: 12px 14px;
}

.score-num {
  width: 60px;
  height: 60px;
  border-radius: 16px;
  display: grid;
  place-items: center;
  font-size: 24px;
  font-weight: 800;
  background: var(--primary-soft);
  color: var(--primary-deep);
}

.dlabel {
  font-size: 12px;
  margin-bottom: 6px;
}

.chips {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.list {
  display: grid;
  gap: 6px;
  max-height: 430px;
  overflow: auto;
}

.item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 9px 10px;
  border-radius: 8px;
  border: 1px solid transparent;
  background: none;
  font: inherit;
  color: inherit;
  cursor: pointer;
  transition: background 0.15s;
}

.item:hover {
  background: var(--surface-2);
}

.item.active {
  background: var(--primary-soft);
  border-color: #cde6df;
}

.dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--border-strong);
  flex: none;
}

.dot.due {
  background: var(--accent);
}

@media (max-width: 900px) {
  .grid[style*='320px'] {
    grid-template-columns: 1fr !important;
  }
  .grid.cols-4 {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
