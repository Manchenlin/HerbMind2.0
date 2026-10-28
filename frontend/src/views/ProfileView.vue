<template>
  <div class="crumb">
    <RouterLink to="/">首页</RouterLink> / <RouterLink to="/me">我的</RouterLink> / 学习档案
  </div>
  <h1 class="serif" style="margin-bottom: 6px">学习档案</h1>
  <p class="muted" style="margin-bottom: 22px">
    按三部经典拆解你的掌握度，并给出下一步该练什么。
  </p>

  <div v-if="loading" class="card">
    <p class="muted">正在汇总你的学习记录…</p>
  </div>

  <div v-else-if="error" class="card">
    <p class="muted" style="color: #a32d2d; margin-bottom: 12px">{{ error }}</p>
    <button class="btn ghost sm" @click="load">重试</button>
  </div>

  <template v-else-if="profile">
    <!-- 顶部概览 -->
    <section class="grid cols-4 stagger" style="margin-bottom: 22px">
      <div class="stat">
        <div class="n"><span class="count">{{ profile.summary.answers }}</span><span class="unit">题</span></div>
        <div class="l">完成练习</div>
      </div>
      <div class="stat">
        <div class="n"><span class="count">{{ profile.summary.litNodes }}</span></div>
        <div class="l">点亮的方证节点</div>
      </div>
      <div class="stat">
        <div class="n"><span class="count">{{ profile.summary.streakDays }}</span><span class="unit">天</span></div>
        <div class="l">连续打卡</div>
      </div>
      <div class="stat">
        <div class="n"><span class="count">{{ profile.summary.mastery }}</span><span class="unit">%</span></div>
        <div class="l">综合掌握度</div>
      </div>
    </section>

    <div class="grid" style="grid-template-columns: 340px 1fr">
      <!-- 雷达 -->
      <section class="card" style="align-self: start">
        <h3 style="margin-bottom: 6px">综合能力雷达</h3>

        <template v-if="!radarEmpty">
          <RadarChart :items="profile.radar" :size="300" />
          <p class="muted" style="font-size: 12px; margin: 8px 0 0; text-align: center">
            按答题得分与练习分布计算
          </p>
        </template>

        <div v-else class="radar-empty">
          <div class="radar-empty-ic">◎</div>
          <p class="muted" style="font-size: 13px">
            还没有练习数据。<br />做完第一道题，这里会长出你的能力雷达。
          </p>
          <RouterLink class="btn primary sm" to="/train">去练习台</RouterLink>
        </div>
      </section>

      <section style="display: grid; gap: 16px; align-content: start">
        <!-- 三经典掌握度 -->
        <div class="card">
          <h3 style="margin-bottom: 14px">三经典掌握度</h3>

          <div v-for="(c, i) in profile.classics" :key="c.key" class="classic">
            <div class="classic-head">
              <span>
                《{{ c.title }}》
                <em class="st" :class="{ off: c.status === '未开始' }">{{ c.status }}</em>
              </span>
              <b v-if="c.status !== '未开始'">{{ c.mastery }}%</b>
              <b v-else class="muted" style="font-weight: 600">未练习</b>
            </div>
            <div class="bar">
              <div class="fill" :style="{ width: `${c.mastery}%`, background: barColor(i) }" />
            </div>
            <div class="muted" style="font-size: 12px; margin-top: 4px">
              已练 {{ c.practiced }} / {{ c.total }} 个单元<template v-if="c.answers > 0"> · 累计 {{ c.answers }} 题</template>
            </div>
          </div>

          <p v-if="!profile.classics.length" class="muted" style="font-size: 13px">
            库里还没有可练的经典单元。
          </p>
        </div>

        <!-- 推荐路径 -->
        <div class="card">
          <h3 style="margin-bottom: 12px">
            推荐学习路径
            <span class="chip primary" style="font-size: 11px">同书续练优先 · 未练单元</span>
          </h3>

          <div v-if="profile.path.length" class="stagger" style="display: grid; gap: 10px">
            <div v-for="p in profile.path" :key="p.nodeId" class="rowitem">
              <span class="thumb">{{ p.step }}</span>
              <div style="flex: 1">
                <b>{{ p.title }}</b>
                <div class="muted">{{ p.reason }}</div>
              </div>
              <RouterLink
                class="btn ghost sm"
                :to="{ path: '/train', query: { node: p.nodeId } }"
              >
                去练
              </RouterLink>
            </div>
          </div>

          <div v-else class="muted" style="font-size: 13.5px">
            所有可练单元都已经练过一遍了。换一本经典，或者重练薄弱单元。
          </div>

          <RouterLink class="btn primary sm" style="margin-top: 14px" to="/train">
            打开练习台
          </RouterLink>
        </div>

        <!-- 薄弱点 -->
        <div class="card">
          <h3 style="margin-bottom: 10px">薄弱点</h3>

          <div v-if="profile.weakPoints.length" class="chips">
            <span v-for="w in profile.weakPoints" :key="w" class="chip accent">{{ w }}</span>
          </div>
          <p v-else class="muted" style="font-size: 13px">
            还没有漏答记录 —— 做几道题，这里会列出你反复遗漏的症象。
          </p>
          <p class="muted" style="font-size: 12px; margin-top: 8px">
            来自评分时被判为「遗漏」的症状词，按出现次数排序。
          </p>
        </div>
      </section>
    </div>
  </template>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import RadarChart from '@/components/RadarChart.vue'
import { getMeProfile, type MeProfile } from '@/api/me'

const profile = ref<MeProfile | null>(null)
const loading = ref(true)
const error = ref('')

const radarEmpty = computed(
  () =>
    !profile.value ||
    profile.value.radar.length === 0 ||
    profile.value.radar.every((d) => (d.value ?? 0) === 0)
)

/** 三条进度条用不同色，与原型一致（主色 / 青 / 金） */
function barColor(i: number) {
  const colors = ['var(--primary)', '#4F8A8B', 'var(--gold)']
  return colors[i % colors.length]
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    profile.value = await getMeProfile()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.stat .n .unit {
  font-size: 15px;
  font-weight: 700;
  margin-left: 3px;
  color: var(--text-2);
  font-family: inherit;
}

.classic {
  margin-bottom: 14px;
}

.classic:last-of-type {
  margin-bottom: 0;
}

.classic-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 8px;
}

.classic-head .st {
  font-style: normal;
  font-size: 11px;
  margin-left: 6px;
  padding: 1px 6px;
  border-radius: 999px;
  background: var(--primary-soft);
  color: var(--primary-deep);
}

.classic-head .st.off {
  background: var(--surface-2);
  color: var(--text-3);
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
  transition: width 0.5s cubic-bezier(0.22, 1, 0.36, 1);
}

.chips {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.radar-empty {
  padding: 26px 12px 22px;
  text-align: center;
  display: grid;
  gap: 10px;
  justify-items: center;
}

.radar-empty-ic {
  width: 52px;
  height: 52px;
  border-radius: 50%;
  background: var(--surface-2);
  color: var(--text-3);
  display: grid;
  place-items: center;
  font-size: 24px;
}

@media (max-width: 900px) {
  .grid[style*='340px'] {
    grid-template-columns: 1fr !important;
  }
  .grid.cols-4 {
    grid-template-columns: 1fr 1fr;
  }
}
</style>
