<template>
  <div class="crumb"><RouterLink to="/">首页</RouterLink> / 练习</div>
  <h1 class="serif" style="margin-bottom: 6px">练习台 · 先思后看</h1>
  <p class="muted" style="margin-bottom: 22px">
    看案例先辨证处方，提交后逐条评分，再与原著对照。
  </p>

  <div v-if="loading" class="card">
    <p class="muted">正在加载练习内容…</p>
  </div>

  <div v-else-if="error" class="card">
    <p class="muted" style="color: #a32d2d; margin-bottom: 12px">{{ error }}</p>
    <button class="btn ghost sm" @click="load">重试</button>
  </div>

  <template v-else>
    <!-- 三种练法 -->
    <div class="grid cols-3" style="margin-bottom: 26px">
      <div class="card link" style="cursor: pointer" @click="start">
        <div style="font-size: 26px">📖</div>
        <h3 style="margin: 8px 0 4px">按方证单元练习</h3>
        <p class="muted">选经典与方证类，按单元出题，先思后看。</p>
      </div>
      <RouterLink class="card link" to="/train/blindbox">
        <div style="font-size: 26px">🎲</div>
        <h3 style="margin: 8px 0 4px">案例盲盒</h3>
        <p class="muted">随机抽一个医案，先答再看。</p>
      </RouterLink>
      <RouterLink class="card link" to="/train/recite">
        <div style="font-size: 26px">📝</div>
        <h3 style="margin: 8px 0 4px">背诵打卡</h3>
        <p class="muted">条文默写 + 间隔重复（SRS）。</p>
      </RouterLink>
    </div>

    <div class="grid cols-2">
      <!-- 选择练习内容 -->
      <section class="card">
        <h3 style="margin-bottom: 12px">选择练习内容</h3>

        <div class="pick">
          <div class="muted">经典</div>
          <div class="chips">
            <span
              v-for="b in books"
              :key="b.id"
              class="chip clickable"
              :class="{ sel: b.id === bookId }"
              @click="selectBook(b.id)"
            >
              {{ b.title }}
            </span>
          </div>
        </div>

        <div class="pick">
          <div class="muted">方证类</div>
          <div class="chips">
            <span
              v-for="n in nodes"
              :key="n.id"
              class="chip clickable"
              :class="{ sel: n.id === nodeId }"
              @click="nodeId = n.id"
            >
              {{ n.title }}
              <em v-if="n.practiced" class="tick">已练</em>
            </span>
          </div>
          <p v-if="!nodes.length" class="muted" style="font-size: 13px; margin-top: 6px">
            该经典下还没有可练的方证单元。
          </p>
        </div>

        <div class="pick">
          <div class="muted">模式</div>
          <div class="chips">
            <span
              v-for="m in modes"
              :key="m"
              class="chip clickable"
              :class="{ sel: m === mode }"
              @click="mode = m"
            >
              {{ m }}
            </span>
          </div>
        </div>

        <button
          class="btn primary"
          style="margin-top: 16px"
          :disabled="!nodeId || starting"
          @click="start"
        >
          {{ starting ? '正在出题…' : `开始练习（${currentNode?.formulaCount ?? 0} 题）` }}
        </button>
        <p v-if="startError" class="muted" style="color: #a32d2d; margin-top: 10px">
          {{ startError }}
        </p>
      </section>

      <!-- 最近练习 -->
      <section class="card">
        <h3 style="margin-bottom: 12px">最近练习</h3>

        <div v-if="recent.length" class="stagger" style="display: grid; gap: 10px">
          <div v-for="r in recent" :key="r.sessionId" class="rowitem">
            <span class="thumb">{{ r.score ?? '—' }}</span>
            <div style="flex: 1">
              <b>{{ r.nodeTitle }}</b>
              <div class="muted">
                {{ r.time }} · {{ r.mode }}
                <template v-if="r.score !== null"> · 得分 {{ r.score }}</template>
                <template v-if="r.durationSeconds > 0"> · 用时 {{ dur(r.durationSeconds) }}</template>
                <template v-if="r.inWrongBook"> · 已加入错题本</template>
              </div>
            </div>
          </div>
        </div>

        <div v-else class="muted" style="font-size: 13.5px">
          还没有练习记录。选一个单元，做第一道题。
        </div>

        <RouterLink class="btn ghost sm" style="margin-top: 12px" to="/me/profile">
          查看学习档案 →
        </RouterLink>
      </section>
    </div>
  </template>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getTrainOptions, startSession, type TrainOptions } from '@/api/train'

const router = useRouter()

const data = ref<TrainOptions | null>(null)
const loading = ref(true)
const error = ref('')

const bookId = ref('')
const nodeId = ref('')
const mode = ref('先思后看')

const starting = ref(false)
const startError = ref('')

const books = computed(() => data.value?.books ?? [])
const modes = computed(() => data.value?.modes ?? ['先思后看'])
const recent = computed(() => data.value?.recent ?? [])

/** 当前选中经典下的可练单元 */
const nodes = computed(() => books.value.find((b) => b.id === bookId.value)?.nodes ?? [])
const currentNode = computed(() => nodes.value.find((n) => n.id === nodeId.value))

function selectBook(id: string) {
  bookId.value = id
  nodeId.value = books.value.find((b) => b.id === id)?.nodes[0]?.id ?? ''
}

function dur(seconds: number) {
  if (!seconds) return '0″'
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return m > 0 ? `${m}′${String(s).padStart(2, '0')}″` : `${s}″`
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const res = await getTrainOptions()
    data.value = res
    mode.value = res.modes?.[0] ?? '先思后看'
    if (res.books?.length) {
      selectBook(res.books[0].id)
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

async function start() {
  if (!nodeId.value || starting.value) return
  starting.value = true
  startError.value = ''
  try {
    const q = await startSession(nodeId.value, mode.value)
    // 题面交给答题页；刷新后仍可读（sessionStorage），避免重复开会话
    sessionStorage.setItem('hm_question', JSON.stringify(q))
    router.push(`/train/session/${q.sessionId}`)
  } catch (e) {
    startError.value = e instanceof Error ? e.message : '出题失败，请换个单元试试'
  } finally {
    starting.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.pick {
  margin-bottom: 14px;
}

.pick .muted {
  margin-bottom: 6px;
}

.chips {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.chip.clickable {
  cursor: pointer;
}

.chip .tick {
  font-style: normal;
  font-size: 10px;
  margin-left: 4px;
  padding: 0 4px;
  border-radius: 4px;
  background: var(--primary-soft);
  color: var(--primary-deep);
}

@media (max-width: 900px) {
  .grid.cols-2,
  .grid.cols-3 {
    grid-template-columns: 1fr;
  }
}
</style>
