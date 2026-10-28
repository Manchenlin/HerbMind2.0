<template>
  <div class="crumb">
    <RouterLink to="/">首页</RouterLink> / <RouterLink to="/train">练习</RouterLink> / 答题
  </div>

  <!-- 没有题面：直接访问 URL 或会话过期 -->
  <div v-if="!question" class="card">
    <h3 style="margin-bottom: 8px">这道题已经失效了</h3>
    <p class="muted" style="margin-bottom: 14px">
      题面只保存在本次练习里，刷新或直接打开链接会丢失。回练习台重新选一个单元即可。
    </p>
    <RouterLink class="btn primary sm" to="/train">回练习台</RouterLink>
  </div>

  <template v-else>
    <div class="title-row">
      <h1 class="serif" style="font-size: 24px">
        {{ question.nodeTitle || '练习' }} · 第 {{ question.index }} / {{ question.total }} 题
      </h1>
      <div class="muted">
        <span v-if="question.bookTitle">{{ question.bookTitle }} · </span>
        <span class="mono">{{ clock }}</span>
      </div>
    </div>

    <div class="grid" style="grid-template-columns: 1fr 300px">
      <section>
        <!-- 题面（无方名） -->
        <div class="card" style="margin-bottom: 16px">
          <h3 style="margin-bottom: 10px">案例原文</h3>
          <p><b>症象：</b>{{ question.symptoms || '（该案例未录入症状描述）' }}</p>
          <p v-if="question.signs" style="margin-top: 8px"><b>舌脉：</b>{{ question.signs }}</p>
        </div>

        <!-- 作答区 -->
        <div v-if="!score" class="card">
          <h3 style="margin-bottom: 4px">请作答（先思后看）</h3>
          <p class="muted" style="margin-bottom: 16px">
            先写出辨证、治法与处方，提交后才揭晓原著答案并评分。
          </p>

          <div style="margin-bottom: 14px">
            <div class="muted" style="margin-bottom: 6px">① 辨证（证候判断）</div>
            <input
              v-model="form.syndrome"
              class="input"
              placeholder="如：太阳伤寒表实证（风寒束表）"
            />
          </div>

          <div style="margin-bottom: 14px">
            <div class="muted" style="margin-bottom: 6px">② 立法 · 治法</div>
            <input v-model="form.treatment" class="input" placeholder="如：辛温解表，宣肺平喘" />
          </div>

          <div style="margin-bottom: 14px">
            <div class="muted" style="margin-bottom: 6px">③ 处方（药味 + 剂量）</div>
            <textarea
              v-model="form.prescription"
              class="input"
              rows="3"
              placeholder="如：麻黄 9g、桂枝 6g、杏仁 9g、炙甘草 3g"
            />
            <p class="muted" style="font-size: 12px; margin-top: 4px">
              用「、」或逗号分隔，剂量可省略。
            </p>
          </div>

          <p v-if="submitError" class="muted" style="color: #a32d2d; margin-bottom: 10px">
            {{ submitError }}
          </p>

          <div style="display: flex; gap: 10px; flex-wrap: wrap">
            <button class="btn primary" :disabled="submitting" @click="submit">
              {{ submitting ? '评分中…' : '提交并评分' }}
            </button>
            <!--
              不做「直接看答案」按钮：标准答案只能由评分接口返回，
              在前端点一下就把答案编出来属于假功能。想看答案就提交（可以只填辨证）。
            -->
            <RouterLink class="btn ghost" to="/train">跳过本题</RouterLink>
          </div>
        </div>

        <!-- 评分结果 -->
        <div v-else class="card">
          <div class="score-head">
            <div class="score-num">{{ score.total }}</div>
            <div>
              <h3 style="margin-bottom: 2px">本题得分</h3>
              <div class="muted" style="font-size: 13px">
                辨证 {{ score.syndromeScore }} · 方剂 {{ score.formulaScore }} · 治法
                {{ score.treatmentScore }}
              </div>
            </div>
            <span style="flex: 1"></span>
            <RouterLink class="btn primary sm" :to="`/train/report/${score.answerId}`">
              查看评分报告
            </RouterLink>
            <RouterLink class="btn ghost sm" to="/train">再练一题</RouterLink>
          </div>

          <div class="diffs">
            <div>
              <div class="muted dlabel">命中</div>
              <div class="chips">
                <span v-for="h in score.hit" :key="h" class="chip primary">{{ h }}</span>
                <span v-if="!score.hit.length" class="muted" style="font-size: 13px">无</span>
              </div>
            </div>
            <div>
              <div class="muted dlabel">遗漏</div>
              <div class="chips">
                <span v-for="m in score.miss" :key="m" class="chip accent">{{ m }}</span>
                <span v-if="!score.miss.length" class="muted" style="font-size: 13px">无</span>
              </div>
            </div>
            <div>
              <div class="muted dlabel">多余</div>
              <div class="chips">
                <span v-for="e in score.extra" :key="e" class="chip">{{ e }}</span>
                <span v-if="!score.extra.length" class="muted" style="font-size: 13px">无</span>
              </div>
            </div>
          </div>

          <p v-if="score.syndromeScore === 0" class="muted" style="font-size: 12.5px; margin-bottom: 14px">
            辨证得 0：你写的是「{{ form.syndrome }}」，案例症象里没有对应的字面重合。
            这一项目前按<strong>字面</strong>比对，不做语义判断——「怕风」和「恶风」不会被认成同一个词，
            语义评分待接入 Agent（任务 B5）。
          </p>

          <div class="ref">
            <h3 style="font-size: 15px; margin-bottom: 8px">原著对照</h3>
            <p class="muted" style="font-size: 13.5px">{{ score.refText }}</p>
          </div>

          <p class="muted" style="font-size: 12px; margin-top: 12px">
            方剂分由药味集合比对得出（可靠）；辨证与治法为关键词重合度，只作参考 ——
            语义评分待接入 Agent（任务 B5）。
          </p>
        </div>
      </section>

      <!-- 侧栏 -->
      <aside style="display: grid; gap: 16px; align-self: start">
        <div class="card">
          <h3 style="font-size: 15px; margin-bottom: 8px">审题提示</h3>
          <p class="muted" style="font-size: 13px">{{ question.hint }}</p>
        </div>

        <div class="card">
          <h3 style="font-size: 15px; margin-bottom: 8px">进度</h3>
          <div class="muted">
            {{ score ? '本题已完成' : '已答 0' }} · 本组：{{ question.nodeTitle }}
          </div>
          <div class="bar" style="margin-top: 10px">
            <div class="fill" :style="{ width: score ? '100%' : '6%' }" />
          </div>
        </div>

        <!--
          这里原本用原型里的 .reveal 做"揭晓"动画，但 theme.css 的 .reveal 默认是
          clip-path: inset(0 0 100% 0) 完全裁掉，需要 JS 加 .show 才显示；
          Vue 项目没有移植那段逻辑，直接用它会让整张卡片看不见。
        -->
        <div class="card">
          <h3 style="font-size: 15px; margin-bottom: 8px">原著答案</h3>
          <p v-if="score" class="muted" style="font-size: 13px">{{ score.refText }}</p>
          <p v-else class="muted" style="font-size: 13px">提交作答后揭晓。</p>
        </div>
      </aside>
    </div>
  </template>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import {
  submitAnswer,
  type AnswerScore,
  type HerbItem,
  type PracticeQuestion
} from '@/api/train'

const route = useRoute()

const question = ref<PracticeQuestion | null>(null)
const score = ref<AnswerScore | null>(null)

const form = reactive({ syndrome: '', treatment: '', prescription: '' })
const submitting = ref(false)
const submitError = ref('')

/* 计时：从进入页面开始 */
const seconds = ref(0)
let timer: number | undefined

const clock = computed(() => {
  const m = String(Math.floor(seconds.value / 60)).padStart(2, '0')
  const s = String(seconds.value % 60).padStart(2, '0')
  return `${m}:${s}`
})

/**
 * 解析处方文本 → HerbItem[]。
 * 支持「麻黄 9g、桂枝 6g」「麻黄9克 桂枝6克」这类写法，剂量与单位可省略。
 */
function parsePrescription(text: string): HerbItem[] {
  const items: HerbItem[] = []
  const chunks = text
    .split(/[、,，;；\n]+/)
    .map((s) => s.trim())
    .filter(Boolean)

  for (const raw of chunks) {
    const m = raw.match(/^([\u4e00-\u9fa5A-Za-z·]{1,12})\s*(\d+(?:\.\d+)?)?\s*(g|kg|克|钱|两|枚|片|个)?/)
    if (!m) continue
    const herb = m[1].trim()
    if (!herb) continue
    items.push({
      herb,
      dose: m[2] ? Number(m[2]) : null,
      unit: m[3] ?? 'g'
    })
  }
  return items
}

async function submit() {
  if (!question.value || submitting.value) return
  if (!form.syndrome.trim()) {
    submitError.value = '请先写出你的辨证'
    return
  }
  const prescription = parsePrescription(form.prescription)
  if (!prescription.length) {
    submitError.value = '请至少写一味药，格式如「麻黄 9g、桂枝 6g」'
    return
  }

  submitting.value = true
  submitError.value = ''
  try {
    score.value = await submitAnswer({
      sessionId: question.value.sessionId,
      syndrome: form.syndrome.trim(),
      treatment: form.treatment.trim(),
      prescription
    })
  } catch (e) {
    submitError.value = e instanceof Error ? e.message : '评分失败，请稍后重试'
  } finally {
    submitting.value = false
  }
}

onMounted(() => {
  const raw = sessionStorage.getItem('hm_question')
  if (raw) {
    try {
      const q = JSON.parse(raw) as PracticeQuestion
      // URL 里的 sessionId 与缓存不一致（比如打开了别的题），以缓存为准但校验一下
      if (!route.params.sessionId || q.sessionId === route.params.sessionId) {
        question.value = q
      }
    } catch {
      question.value = null
    }
  }
  timer = window.setInterval(() => {
    seconds.value += 1
  }, 1000)
})

onUnmounted(() => {
  if (timer) window.clearInterval(timer)
})
</script>

<style scoped>
.title-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
  flex-wrap: wrap;
}

.score-head {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
  margin-bottom: 18px;
}

.score-num {
  width: 64px;
  height: 64px;
  border-radius: 18px;
  display: grid;
  place-items: center;
  font-size: 26px;
  font-weight: 800;
  background: var(--primary-soft);
  color: var(--primary-deep);
}

.diffs {
  display: grid;
  gap: 12px;
  margin-bottom: 18px;
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

.ref {
  border-top: 1px solid var(--line);
  padding-top: 14px;
}

.bar {
  height: 8px;
  background: var(--surface-2);
  border-radius: 8px;
  overflow: hidden;
}

.bar .fill {
  height: 100%;
  background: var(--primary);
  border-radius: 8px;
  transition: width 0.4s ease;
}

@media (max-width: 900px) {
  .grid[style*='300px'] {
    grid-template-columns: 1fr !important;
  }
}
</style>
