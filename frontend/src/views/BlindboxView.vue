<template>
  <div class="crumb">
    <RouterLink to="/">首页</RouterLink> / <RouterLink to="/train">练习</RouterLink> / 案例盲盒
  </div>
  <h1 class="serif" style="margin-bottom: 6px">案例盲盒 🎲</h1>
  <p class="muted" style="margin-bottom: 22px">
    随机抽取一个医案，先辨证处方，再揭晓原著。像开盲盒一样学方证。
  </p>

  <div class="grid" style="grid-template-columns: 1fr 300px">
    <section class="card" style="min-height: 320px">
      <!-- 空态 -->
      <div v-if="!box" class="center" style="padding: 60px 0">
        <div style="font-size: 56px">🎁</div>
        <p class="muted" style="margin: 16px 0 20px">
          {{ drawing ? '正在抽…' : '点击下方按钮，随机抽取一个医案' }}
        </p>
        <button class="btn primary" :disabled="drawing" @click="draw">抽取盲盒</button>
        <p v-if="error" class="muted" style="color: #a32d2d; margin-top: 14px">{{ error }}</p>
      </div>

      <!-- 已抽到 -->
      <div v-else>
        <div style="display: flex; justify-content: space-between; align-items: center; gap: 10px">
          <h3>{{ box.title || '未命名医案' }}</h3>
          <span class="chip gold">盲盒</span>
        </div>
        <p class="muted" style="margin: 10px 0 4px">{{ box.bookTitle }} · {{ box.nodeTitle }}</p>
        <p style="margin: 12px 0; line-height: 1.85">
          <b>案例原文：</b>{{ box.illness || '（该案例未录入原文）' }}
        </p>
        <p v-if="box.exam" class="muted"><b>舌脉：</b>{{ box.exam }}</p>

        <div class="hr"></div>

        <!-- 揭晓前是遮罩，揭晓后才显示 -->
        <div v-if="answer" class="reveal-box">
          <p><b>辨证：</b>{{ answer.syndromeText || '—' }}</p>
          <p style="margin-top: 8px"><b>治法：</b>{{ answer.efficacy || '—' }}</p>
          <p style="margin-top: 8px">
            <b>处方：</b>
            <span v-if="answer.prescription.length">{{ answer.prescription.join('、') }}</span>
            <span v-else>该方未录入药味组成</span>
          </p>
          <p class="muted" style="margin-top: 8px; font-size: 12.5px">
            参考方：{{ answer.formulaName }}
          </p>
        </div>
        <div v-else class="masked">
          <p class="muted">答案已遮住 —— 先自己辨证立法，再揭晓。</p>
          <button class="btn accent sm" :disabled="revealing" @click="reveal">
            {{ revealing ? '揭晓中…' : '揭晓答案' }}
          </button>
        </div>

        <div style="display: flex; gap: 10px; margin-top: 16px; flex-wrap: wrap">
          <button class="btn ghost" :disabled="drawing" @click="draw">换一个</button>
          <button class="btn primary" :disabled="answering" @click="answerMyself">
            {{ answering ? '正在出题…' : '我也答一遍' }}
          </button>
        </div>
        <p v-if="answerError" class="muted" style="color: #a32d2d; margin-top: 10px">
          {{ answerError }}
        </p>
      </div>
    </section>

    <aside style="display: grid; gap: 16px; align-self: start">
      <div class="card">
        <h3 style="font-size: 15px; margin-bottom: 8px">玩法说明</h3>
        <ol class="muted" style="font-size: 13px; padding-left: 18px; line-height: 2">
          <li>随机抽一个医案</li>
          <li>先自己辨证、立法、处方</li>
          <li>揭晓原著答案对照</li>
          <li>点「我也答一遍」进入评分，低分自动进错题本</li>
        </ol>
      </div>
      <div class="card">
        <h3 style="font-size: 15px; margin-bottom: 8px">盲盒战绩</h3>
        <div class="muted">
          已练 {{ box?.drawnCount ?? stats.drawnCount }} 个
          <template v-if="avg !== null"> · 平均 {{ avg }} 分</template>
          <template v-else> · 还没有评分记录</template>
        </div>
        <p class="muted" style="font-size: 12px; margin-top: 8px">
          只统计真的提交过作答的盲盒；抽了没答不算。
        </p>
      </div>
    </aside>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  drawBlindbox,
  revealBlindbox,
  startSession,
  type Blindbox,
  type BlindboxAnswer
} from '@/api/train'

const router = useRouter()

const box = ref<Blindbox | null>(null)
const answer = ref<BlindboxAnswer | null>(null)
const stats = ref({ drawnCount: 0, avgScore: null as number | null })

const drawing = ref(false)
const revealing = ref(false)
const answering = ref(false)
const error = ref('')
const answerError = ref('')

/** 抽过一次之后，战绩以最近一次返回为准（后端每次都会带最新统计） */
const avg = computed(() => (box.value ? box.value.avgScore : stats.value.avgScore))

async function draw() {
  if (drawing.value) return
  drawing.value = true
  error.value = ''
  try {
    const res = await drawBlindbox()
    box.value = res
    answer.value = null
    stats.value = { drawnCount: res.drawnCount, avgScore: res.avgScore }
  } catch (e) {
    error.value = e instanceof Error ? e.message : '抽取失败，请稍后重试'
  } finally {
    drawing.value = false
  }
}

async function reveal() {
  if (!box.value || revealing.value) return
  revealing.value = true
  try {
    answer.value = await revealBlindbox(box.value.caseId, box.value.formulaId)
  } catch (e) {
    error.value = e instanceof Error ? e.message : '揭晓失败'
  } finally {
    revealing.value = false
  }
}

/**
 * 进入答题：带 formulaId 开一个 mode=盲盒 的会话，
 * 这样练习统计、错题本、评分报告全部复用同一条链路。
 */
async function answerMyself() {
  if (!box.value || answering.value) return
  answering.value = true
  answerError.value = ''
  try {
    const q = await startSession(box.value.nodeId, '盲盒', box.value.formulaId)
    sessionStorage.setItem('hm_question', JSON.stringify(q))
    router.push(`/train/session/${q.sessionId}`)
  } catch (e) {
    answerError.value = e instanceof Error ? e.message : '出题失败，换个盲盒试试'
  } finally {
    answering.value = false
  }
}
</script>

<style scoped>
.masked {
  background: var(--surface-2);
  border: 1px dashed var(--border-strong);
  border-radius: var(--radius);
  padding: 18px;
  text-align: center;
}

.masked .muted {
  margin-bottom: 12px;
}

.reveal-box {
  background: var(--primary-soft);
  border-radius: var(--radius);
  padding: 16px 18px;
  font-size: 14px;
}

@media (max-width: 900px) {
  .grid[style*='300px'] {
    grid-template-columns: 1fr !important;
  }
}
</style>
