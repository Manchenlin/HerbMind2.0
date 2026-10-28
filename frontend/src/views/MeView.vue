<template>
  <div class="crumb"><RouterLink to="/">首页</RouterLink> / 我的</div>

  <!-- 加载 / 错误 -->
  <div v-if="loading" class="card">
    <p class="muted">正在加载你的学习记录…</p>
  </div>

  <div v-else-if="error" class="card">
    <p class="muted" style="color:#A32D2D;margin-bottom:12px">{{ error }}</p>
    <button class="btn ghost sm" @click="load">重试</button>
  </div>

  <template v-else-if="dash">
    <!-- 顶部：头像 + 昵称 + 学习概况 -->
    <div class="me-head">
      <div class="me-avatar">{{ initial }}</div>
      <div>
        <h1 class="serif" style="font-size:22px">{{ nickname }}</h1>
        <div class="muted">{{ subtitle }}</div>
      </div>
      <span style="flex:1"></span>
      <RouterLink class="btn ghost sm" to="/me/profile">学习档案 →</RouterLink>
    </div>

    <!-- 四宫格 -->
    <section class="grid cols-4 stagger" style="margin-bottom:26px">
      <div class="stat">
        <div class="n">
          <span class="count">{{ nums.duration }}</span><span class="unit">{{ durationUnit }}</span>
        </div>
        <div class="l">累计学习时长</div>
      </div>
      <div class="stat">
        <div class="n"><span class="count">{{ nums.streak }}</span><span class="unit">天</span></div>
        <div class="l">连续打卡</div>
      </div>
      <div class="stat">
        <div class="n"><span class="count">{{ nums.mastery }}</span><span class="unit">%</span></div>
        <div class="l">综合掌握度</div>
      </div>
      <div class="stat">
        <div class="n"><span class="count">{{ nums.lit }}</span></div>
        <div class="l">已点亮的方证节点</div>
      </div>
    </section>

    <div class="grid" style="grid-template-columns:320px 1fr">
      <!-- 能力雷达 -->
      <section class="card" style="align-self:start">
        <h3 style="margin-bottom:6px">能力雷达</h3>

        <template v-if="radar.length && !radarEmpty">
          <svg
            :viewBox="`${RADAR_PAD} ${RADAR_PAD} ${RADAR_SIZE - RADAR_PAD * 2} ${RADAR_SIZE - RADAR_PAD * 2}`"
            style="width:100%;margin-top:6px"
          >
            <!-- 底环 -->
            <polygon
              v-for="k in [0.5, 1]"
              :key="k"
              class="radar-ring"
              :points="ringPoints(k)"
            />
            <!-- 轴线 + 维度名 -->
            <g v-for="(d, i) in radar" :key="d.key">
              <line
                :x1="RADAR_C"
                :y1="RADAR_C"
                :x2="axisPoint(i).x"
                :y2="axisPoint(i).y"
                stroke="#ECECE8"
              />
              <text
                :x="labelPoint(i).x"
                :y="labelPoint(i).y"
                text-anchor="middle"
                font-size="10.5"
                fill="#6B7280"
              >
                {{ d.label }}
              </text>
            </g>
            <!-- 能力形状 -->
            <polygon class="radar-shape" :points="shapePoints()" />
          </svg>
          <p class="muted" style="font-size:12px;margin:8px 0 12px;text-align:center">
            按答题得分与练习分布计算
          </p>
        </template>

        <!-- 空态：还没练过 -->
        <div v-else class="radar-empty">
          <div class="radar-empty-ic">◎</div>
          <p class="muted" style="font-size:13px">
            还没有练习数据。<br />完成 3 道题后，这里会长出你的能力雷达。
          </p>
          <RouterLink class="btn primary sm" to="/train">去练习台</RouterLink>
        </div>

        <RouterLink
          v-if="!radarEmpty"
          class="btn ghost sm"
          style="width:100%;justify-content:center"
          to="/me/profile"
        >
          查看完整学习档案 →
        </RouterLink>
      </section>

      <section style="display:grid;gap:16px;align-content:start">
        <!-- 快捷入口 -->
        <div class="card">
          <h3 style="margin-bottom:12px">快捷入口</h3>
          <div class="grid cols-3">
            <RouterLink class="rowitem" to="/me/favorites">
              <span class="thumb">★</span>
              <div>
                <b>收藏夹</b>
                <div class="muted">{{ shortcuts.favorites }} 条</div>
              </div>
            </RouterLink>
            <RouterLink class="rowitem" to="/me/notes">
              <span class="thumb">✎</span>
              <div>
                <b>我的笔记</b>
                <div class="muted">{{ shortcuts.notes }} 条</div>
              </div>
            </RouterLink>
            <RouterLink class="rowitem" to="/me/wrong">
              <span class="thumb">✗</span>
              <div>
                <b>错题本</b>
                <div class="muted">{{ shortcuts.wrong }} 题待复习</div>
              </div>
            </RouterLink>
          </div>

          <div class="grid cols-3" style="margin-top:10px">
            <RouterLink class="rowitem" to="/me/collection">
              <span class="thumb">方</span>
              <div>
                <b>我的方证库</b>
                <div class="muted">按方看掌握度</div>
              </div>
            </RouterLink>
            <RouterLink class="rowitem" to="/me/path">
              <span class="thumb">路</span>
              <div>
                <b>学习路径</b>
                <div class="muted">下一步练什么</div>
              </div>
            </RouterLink>
            <RouterLink class="rowitem" to="/discuss">
              <span class="thumb">💬</span>
              <div>
                <b>讨论区</b>
                <div class="muted">方证辨疑</div>
              </div>
            </RouterLink>
          </div>
        </div>

        <!-- 成长时间轴 -->
        <div class="card">
          <h3 style="margin-bottom:12px">成长时间轴</h3>

          <div v-if="timeline.length" class="timeline">
            <div v-for="(t, i) in timeline" :key="i" class="ev">
              <b>{{ t.time }}</b> · {{ t.text }}
            </div>
          </div>

          <div v-else class="muted" style="font-size:13.5px">
            还没有学习记录。做一次练习、收藏一个方剂，这里就会开始记下你的轨迹。
            <RouterLink to="/train" style="color:var(--primary-deep);font-weight:600">
              去练习台 →
            </RouterLink>
          </div>
        </div>
      </section>
    </div>
  </template>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { getMeDashboard, type MeDashboard, type RadarItem } from '@/api/me'

/* ---------- 状态 ---------- */
const dash = ref<MeDashboard | null>(null)
const loading = ref(true)
const error = ref('')

/* 数字滚动（原型里的 data-count 动效） */
const nums = reactive({ duration: 0, streak: 0, mastery: 0, lit: 0 })

/* ---------- 派生 ---------- */
const stats = computed(() => dash.value?.stats)
const radar = computed<RadarItem[]>(() => dash.value?.radar ?? [])
const timeline = computed(() => dash.value?.timeline ?? [])
const shortcuts = computed(
  () => dash.value?.shortcuts ?? { favorites: 0, notes: 0, wrong: 0 }
)

const nickname = computed(
  () => dash.value?.user?.nickname || dash.value?.user?.username || '学习者'
)
const initial = computed(() => nickname.value.slice(0, 1))

/** 时长：满 60 分钟按小时展示，否则按分钟 */
const durationView = computed(() => {
  const m = stats.value?.totalMinutes ?? 0
  return m >= 60 ? { value: Math.round(m / 60), unit: 'h' } : { value: m, unit: 'min' }
})
const durationUnit = computed(() => durationView.value.unit)

const subtitle = computed(() => {
  const s = stats.value
  if (!s || s.answerCount === 0) {
    return '还没有练习记录 · 做完第一道题，这里就会开始记录你的成长'
  }
  return `综合掌握度 ${s.mastery}% · 已完成 ${s.answerCount} 题练习 · 点亮 ${s.litNodes} 个方证`
})

/* ---------- 雷达几何（与原型 me.html 同一套算法） ---------- */
const RADAR_SIZE = 300
const RADAR_C = 150
const RADAR_R = 100
/** 裁掉图形四周的空白，让雷达在卡片里显得更饱满（不要裁太狠，否则维度名会贴上标题） */
const RADAR_PAD = 14

const radarEmpty = computed(
  () => radar.value.length === 0 || radar.value.every((d) => (d.value ?? 0) === 0)
)

function angleOf(i: number, n: number) {
  return -Math.PI / 2 + (i * 2 * Math.PI) / n
}

/** 底环（等比缩放的多边形） */
function ringPoints(k: number) {
  const n = radar.value.length
  return radar.value
    .map((_, i) => {
      const a = angleOf(i, n)
      return `${RADAR_C + RADAR_R * k * Math.cos(a)},${RADAR_C + RADAR_R * k * Math.sin(a)}`
    })
    .join(' ')
}

/** 能力形状（按各维 value 0-100 缩放） */
function shapePoints() {
  const n = radar.value.length
  return radar.value
    .map((d, i) => {
      const a = angleOf(i, n)
      const v = Math.max(0, Math.min(100, d.value ?? 0))
      const r = (RADAR_R * v) / 100
      return `${RADAR_C + r * Math.cos(a)},${RADAR_C + r * Math.sin(a)}`
    })
    .join(' ')
}

function axisPoint(i: number) {
  const a = angleOf(i, radar.value.length)
  return { x: RADAR_C + RADAR_R * Math.cos(a), y: RADAR_C + RADAR_R * Math.sin(a) }
}

function labelPoint(i: number) {
  const a = angleOf(i, radar.value.length)
  const r = RADAR_R + 22
  return { x: RADAR_C + r * Math.cos(a), y: RADAR_C + r * Math.sin(a) }
}

/* ---------- 数字滚动 ---------- */
function animateTo(target: typeof nums) {
  const from = { ...nums }
  const start = performance.now()
  const dur = 420
  const step = (now: number) => {
    const t = Math.min(1, (now - start) / dur)
    const e = 1 - Math.pow(1 - t, 3) // easeOutCubic
    ;(Object.keys(nums) as Array<keyof typeof nums>).forEach((k) => {
      nums[k] = Math.round(from[k] + (target[k] - from[k]) * e)
    })
    if (t < 1) requestAnimationFrame(step)
  }
  requestAnimationFrame(step)
}

/* ---------- 加载 ---------- */
async function load() {
  loading.value = true
  error.value = ''
  try {
    const data = await getMeDashboard()
    dash.value = data
    const s = data.stats
    animateTo({
      duration: durationView.value.value,
      streak: s?.streakDays ?? 0,
      mastery: s?.mastery ?? 0,
      lit: s?.litNodes ?? 0
    })
  } catch (e) {
    // request.ts 已把 R 的 msg 抛成 Error；401 会被拦截器处理跳登录
    error.value = e instanceof Error ? e.message : '加载失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
/* 只补充原型里用内联样式写死的尺寸，颜色一律走 theme.css 的变量 */
.me-head {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 22px;
}

.me-avatar {
  width: 56px;
  height: 56px;
  border-radius: 16px;
  flex: none;
  background: var(--primary-soft);
  color: var(--primary-deep);
  display: grid;
  place-items: center;
  font-weight: 800;
  font-size: 22px;
}

.stat .n .unit {
  font-size: 15px;
  font-weight: 700;
  margin-left: 3px;
  color: var(--text-2);
  font-family: inherit;
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
  .grid[style*='320px'] {
    grid-template-columns: 1fr !important;
  }
}
</style>
