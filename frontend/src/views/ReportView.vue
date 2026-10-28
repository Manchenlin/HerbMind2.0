<template>
  <div class="crumb">
    <RouterLink to="/">首页</RouterLink> / <RouterLink to="/train">练习</RouterLink> / 评分报告
  </div>

  <div v-if="loading" class="card"><p class="muted">正在加载报告…</p></div>
  <div v-else-if="error" class="card">
    <p class="muted" style="color: #a32d2d; margin-bottom: 12px">{{ error }}</p>
    <RouterLink class="btn ghost sm" to="/train">回练习台</RouterLink>
  </div>

  <template v-else-if="r">
    <div class="head">
      <div>
        <h1 class="serif" style="font-size: 24px">
          评分报告 · {{ r.nodeTitle || r.formulaName || '练习' }}
        </h1>
        <div class="muted">
          用时 {{ dur(r.durationSeconds) }} · 提交时间 {{ r.submittedLabel || '—' }}
          <template v-if="r.bookTitle"> · {{ r.bookTitle }}</template>
        </div>
      </div>
      <div style="text-align: right">
        <div class="total">{{ r.total }}</div>
        <div class="muted">总分 / 100</div>
      </div>
    </div>

    <div class="grid" style="grid-template-columns: 320px 1fr">
      <!-- 雷达：累计画像，不是这次的 -->
      <section class="card">
        <h3 style="margin-bottom: 4px">能力画像</h3>
        <p class="muted" style="font-size: 12px; margin-bottom: 8px">
          累计 · 全部练习的平均分项，不是这一次答题
        </p>
        <RadarChart v-if="r.radar.length" :items="r.radar" :size="290" />
        <p v-else class="muted">还没有足够的练习数据。</p>
      </section>

      <section style="display: grid; gap: 16px">
        <!-- 分项 -->
        <div class="card">
          <h3 style="margin-bottom: 14px">分项得分</h3>
          <div v-for="d in dims" :key="d.label" class="dim">
            <div class="dim-head">
              <span>{{ d.label }}</span>
              <b>{{ d.value }}</b>
            </div>
            <div class="bar">
              <div class="fill" :style="{ width: `${d.value}%`, background: d.color }" />
            </div>
          </div>
          <p class="muted" style="font-size: 12px; margin-top: 12px">
            方剂分为药味集合比对（F1，可靠）；辨证与治法为字面重合度，只作参考。
            语义评分待接入 Agent（任务 B5）。
          </p>
        </div>

        <!-- 我的作答 vs 参考 -->
        <div class="card">
          <h3 style="margin-bottom: 12px">我的作答</h3>
          <div class="pair">
            <div>
              <div class="muted dlabel">辨证</div>
              <p>{{ r.userSyndrome || '（没写）' }}</p>
            </div>
            <div>
              <div class="muted dlabel">治法</div>
              <p>{{ r.userTreatment || '（没写）' }}</p>
            </div>
            <div>
              <div class="muted dlabel">处方</div>
              <p>
                <span v-if="r.userPrescription.length">{{ r.userPrescription.join('、') }}</span>
                <span v-else>（没写）</span>
              </p>
            </div>
          </div>
        </div>

        <!-- 药味比对 -->
        <div class="card">
          <h3 style="margin-bottom: 12px">药味比对（F1）</h3>
          <div class="diff">
            <div class="muted dlabel">命中</div>
            <div class="chips">
              <span v-for="h in r.hit" :key="h" class="chip primary">{{ h }}</span>
              <span v-if="!r.hit.length" class="muted">无</span>
            </div>
          </div>
          <div class="diff">
            <div class="muted dlabel">遗漏</div>
            <div class="chips">
              <span v-for="m in r.miss" :key="m" class="chip accent">{{ m }}</span>
              <span v-if="!r.miss.length" class="muted">无</span>
            </div>
          </div>
          <div class="diff">
            <div class="muted dlabel">多余</div>
            <div class="chips">
              <span v-for="x in r.extra" :key="x" class="chip">{{ x }}</span>
              <span v-if="!r.extra.length" class="muted">无</span>
            </div>
          </div>
          <p class="muted" style="font-size: 12px; margin-top: 12px">
            辨证一栏没有做逐条比对 —— 那需要语义理解（B5），现在只有字面覆盖率，
            拿它当"命中/遗漏"展示是不诚实的。
          </p>
        </div>

        <!-- 原著对照 -->
        <div class="card">
          <h3 style="margin-bottom: 10px">原著对照</h3>
          <div class="cite">
            <div>
              <div>{{ r.refText }}</div>
              <div class="pg">
                {{ r.bookTitle }}<template v-if="r.nodeTitle"> · {{ r.nodeTitle }}</template>
              </div>
            </div>
          </div>
          <div style="display: flex; gap: 10px; margin-top: 16px; flex-wrap: wrap">
            <RouterLink class="btn primary sm" to="/train">再做一题</RouterLink>
            <RouterLink class="btn ghost sm" to="/me/wrong">错题本</RouterLink>
            <RouterLink class="btn ghost sm" to="/ask">问 Agent 讲解</RouterLink>
          </div>
        </div>
      </section>
    </div>
  </template>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import RadarChart from '@/components/RadarChart.vue'
import { getReport, type Report } from '@/api/train'

const route = useRoute()
const r = ref<Report | null>(null)
const loading = ref(true)
const error = ref('')

/** 三根进度条：颜色对齐原型（主色 / 青 / 金） */
const dims = computed(() => {
  const d = r.value
  if (!d) return []
  return [
    { label: '辨证（权重 30%）', value: d.syndromeScore, color: 'var(--primary)' },
    { label: '方剂（权重 40%）', value: d.formulaScore, color: '#4F8A8B' },
    { label: '治法（权重 30%）', value: d.treatmentScore, color: 'var(--gold)' }
  ]
})

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
    r.value = await getReport(String(route.params.answerId ?? ''))
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  margin-bottom: 18px;
  flex-wrap: wrap;
}

.total {
  font-size: 44px;
  font-weight: 800;
  font-family: 'Noto Serif SC', serif;
  color: var(--primary-deep);
  line-height: 1.1;
}

.dim {
  margin-bottom: 14px;
}

.dim:last-of-type {
  margin-bottom: 0;
}

.dim-head {
  display: flex;
  justify-content: space-between;
  font-size: 14px;
}

.bar {
  height: 8px;
  background: var(--surface-2);
  border-radius: 8px;
  margin-top: 6px;
  overflow: hidden;
}

.bar .fill {
  height: 100%;
  border-radius: 8px;
  transition: width 0.4s ease;
}

.pair {
  display: grid;
  gap: 12px;
}

.pair p {
  font-size: 14px;
  line-height: 1.75;
}

.dlabel {
  font-size: 12px;
  margin-bottom: 4px;
}

.diff {
  margin-bottom: 12px;
}

.chips {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

@media (max-width: 900px) {
  .grid[style*='320px'] {
    grid-template-columns: 1fr !important;
  }
}
</style>
