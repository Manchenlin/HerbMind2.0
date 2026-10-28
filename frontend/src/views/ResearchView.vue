<template>
  <div class="crumb">
    <RouterLink to="/">首页</RouterLink> / 科研
  </div>

  <div
    style="display:flex;justify-content:space-between;align-items:flex-end;gap:18px;flex-wrap:wrap;margin-bottom:18px"
  >
    <div>
      <h1 class="serif" style="font-size:26px">科研工作台</h1>
      <p class="muted" style="margin-top:4px">用药频次 · 证候分布 · 经典/章节分布，可复现导出。</p>
    </div>
    <div style="display:flex;gap:10px;flex-wrap:wrap">
      <RouterLink class="btn ghost" to="/research/export">数据导出</RouterLink>
      <RouterLink class="btn primary" to="/graph">进入图谱</RouterLink>
    </div>
  </div>

  <div v-if="loading" class="card" style="display:flex;align-items:center;gap:10px">
    <span class="spin"></span>
    <span class="muted">正在加载科研统计数据…</span>
  </div>

  <div v-else-if="error" class="card">
    <h3>科研数据加载失败</h3>
    <p class="muted" style="margin-top:6px">{{ error }}</p>
    <p class="muted" style="margin-top:10px">
      请确认后端已启动（svc-insight :8086 / BFF :8090），且已导入数据快照。
    </p>
    <button class="btn ghost sm" type="button" style="margin-top:14px" @click="load">重试</button>
  </div>

  <template v-else>
    <div class="grid cols-4 stagger">
      <div class="stat">
        <div class="n count">{{ num(totals.units) }}</div>
        <div class="l">内容单元</div>
      </div>
      <div class="stat">
        <div class="n count">{{ num(totals.formulas) }}</div>
        <div class="l">方剂</div>
      </div>
      <div class="stat">
        <div class="n count">{{ num(totals.cases) }}</div>
        <div class="l">医案</div>
      </div>
      <div class="stat">
        <div class="n count">{{ num(totals.quotes) }}</div>
        <div class="l">条文</div>
      </div>
    </div>

    <div class="grid cols-2" style="margin-top:18px">
      <!-- 用药频次 -->
      <section class="card">
        <div style="display:flex;justify-content:space-between;align-items:baseline;gap:10px;flex-wrap:wrap">
          <h3>用药频次 Top 20</h3>
          <span class="muted" style="font-size:12.5px">共 {{ herbs.length }} 味</span>
        </div>
        <p v-if="!herbs.length" class="muted" style="margin-top:12px">
          暂无统计数据（请先导入数据快照）
        </p>
        <div v-else style="margin-top:16px">
          <div
            v-for="h in herbs"
            :key="h.herb"
            :title="`出现 ${h.count} 次 · ${h.formulaCount} 方`"
            style="display:grid;grid-template-columns:60px 1fr 52px;gap:10px;align-items:center;margin-bottom:9px"
          >
            <div
              style="font-size:13px;color:var(--text-2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis"
            >{{ h.herb }}</div>
            <div style="height:10px;border-radius:999px;background:var(--surface-2);overflow:hidden">
              <div
                :style="{
                  width: barWidth(h.count, maxHerb),
                  height: '10px',
                  borderRadius: '999px',
                  background: 'linear-gradient(90deg,var(--primary),#7FB7AC)'
                }"
              ></div>
            </div>
            <div class="mono" style="font-size:12.5px;color:var(--text-2);text-align:right">
              {{ h.count }}
            </div>
          </div>
        </div>
      </section>

      <!-- 证候分布 -->
      <section class="card">
        <div style="display:flex;justify-content:space-between;align-items:baseline;gap:10px;flex-wrap:wrap">
          <h3>证候分布</h3>
          <span class="muted" style="font-size:12.5px">共 {{ syndromes.length }} 类</span>
        </div>
        <p v-if="!syndromes.length" class="muted" style="margin-top:12px">
          暂无统计数据（请先导入数据快照）
        </p>
        <div v-else style="margin-top:16px">
          <div
            v-for="s in syndromes"
            :key="s.key"
            :title="`${s.label} · 出现 ${s.count} 次`"
            style="display:grid;grid-template-columns:120px 1fr 52px;gap:10px;align-items:center;margin-bottom:9px"
          >
            <div
              :title="s.label"
              style="font-size:13px;color:var(--text-2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis"
            >{{ truncate(s.label, 18) }}</div>
            <div style="height:10px;border-radius:999px;background:var(--surface-2);overflow:hidden">
              <div
                :style="{
                  width: barWidth(s.count, maxSyndrome),
                  height: '10px',
                  borderRadius: '999px',
                  background: 'var(--gold)'
                }"
              ></div>
            </div>
            <div class="mono" style="font-size:12.5px;color:var(--text-2);text-align:right">
              {{ s.count }}
            </div>
          </div>
        </div>
      </section>
    </div>

    <!-- 经典 / 章节分布 -->
    <section class="card" style="margin-top:18px">
      <div style="display:flex;justify-content:space-between;align-items:baseline;gap:10px;flex-wrap:wrap">
        <h3>经典 / 章节分布</h3>
        <span class="muted" style="font-size:12.5px">
          以 {{ num(totals.units) }} 个内容单元为分母
        </span>
      </div>
      <p v-if="!books.length && !chapters.length" class="muted" style="margin-top:12px">
        暂无统计数据（请先导入数据快照）
      </p>
      <div v-else class="grid cols-2" style="gap:26px;margin-top:16px">
        <div>
          <div class="muted" style="font-weight:700;color:var(--text);margin-bottom:10px">经典分布</div>
          <p v-if="!books.length" class="muted">暂无统计数据（请先导入数据快照）</p>
          <div v-else>
            <div
              v-for="b in books"
              :key="b.key"
              style="display:flex;align-items:center;justify-content:space-between;gap:10px;padding:8px 0;border-bottom:1px solid var(--border)"
            >
              <span style="font-size:13.5px">{{ b.label }}</span>
              <span style="display:flex;align-items:center;gap:10px">
                <span class="mono muted">{{ num(b.count) }}</span>
                <span class="chip gold">{{ pct(b.ratio) }}</span>
              </span>
            </div>
          </div>
        </div>
        <div>
          <div class="muted" style="font-weight:700;color:var(--text);margin-bottom:10px">
            章节分布 · Top 20
          </div>
          <p v-if="!chapters.length" class="muted">暂无统计数据（请先导入数据快照）</p>
          <table v-else class="tb" style="font-size:13px">
            <thead>
              <tr>
                <th>章节</th>
                <th style="text-align:right">单元</th>
                <th style="text-align:right">占比</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="c in chapters.slice(0, 20)" :key="c.key">
                <td :title="c.label" style="max-width:220px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">
                  {{ c.label }}
                </td>
                <td class="mono" style="text-align:right">{{ num(c.count) }}</td>
                <td class="muted" style="text-align:right">{{ pct(c.ratio) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>

    <!-- 方剂星系 -->
    <section class="card" style="margin-top:18px">
      <h3>方剂星系</h3>
      <p class="muted" style="margin-top:2px">
        按用药频次把 Top 12 药味画成气泡，气泡越大，出现越多。
      </p>
      <p v-if="!herbs.length" class="muted" style="margin-top:12px">
        暂无统计数据（请先导入数据快照）
      </p>
      <template v-else>
        <svg
          viewBox="0 0 860 300"
          role="img"
          aria-label="用药频次气泡分布"
          style="width:100%;height:auto;display:block;margin-top:12px;border-radius:12px;background:radial-gradient(circle at 42% 38%,#FBFCFB,#EEF3F1)"
        >
          <g v-for="b in galaxy" :key="b.herb">
            <title>{{ bubbleTitle(b) }}</title>
            <circle
              :cx="b.x"
              :cy="b.y"
              :r="b.r"
              :fill="b.color"
              fill-opacity="0.16"
              :stroke="b.color"
              stroke-width="1.6"
            />
            <text
              :x="b.x"
              :y="b.y + 3.5"
              text-anchor="middle"
              font-size="10"
              fill="#1F2328"
              style="pointer-events:none"
            >{{ b.text }}</text>
          </g>
        </svg>
        <div class="muted" style="display:flex;gap:18px;flex-wrap:wrap;margin-top:12px;font-size:12.5px">
          <span style="display:inline-flex;align-items:center;gap:6px">
            <span
              style="width:10px;height:10px;border-radius:50%;background:var(--primary);display:inline-block"
            ></span>
            气泡大小 = 出现频次
          </span>
          <span>颜色按频次序列轮换</span>
          <span>固定黄金角分布，仅作示意</span>
        </div>
      </template>
    </section>
  </template>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  getHerbs,
  getSyndrome,
  getTrend,
  type CountItem,
  type HerbStat,
  type Trend
} from '@/api/insight'
import { num } from '@/utils/format'

const herbs = ref<HerbStat[]>([])
const syndromes = ref<CountItem[]>([])
const trend = ref<Trend | null>(null)
const loading = ref(false)
const error = ref('')

const totals = computed(() => ({
  units: trend.value?.totalUnits ?? 0,
  formulas: trend.value?.totalFormulas ?? 0,
  cases: trend.value?.totalCases ?? 0,
  quotes: trend.value?.totalQuotes ?? 0
}))

const books = computed<CountItem[]>(() => trend.value?.books ?? [])
const chapters = computed<CountItem[]>(() => trend.value?.chapters ?? [])

const maxHerb = computed(() => herbs.value.reduce((m, h) => Math.max(m, h.count), 0))
const maxSyndrome = computed(() => syndromes.value.reduce((m, s) => Math.max(m, s.count), 0))

interface Bubble {
  herb: string
  count: number
  formulaCount: number
  x: number
  y: number
  r: number
  color: string
  text: string
}

const GALAXY_COLORS = ['var(--primary)', '#3B7DD8', '#D9724E', '#C8A96A']
const GOLDEN_ANGLE = 2.399963229728653

/** Top 12 药味 → 固定黄金角分布的气泡（仅示意，不做真实降维） */
const galaxy = computed<Bubble[]>(() => {
  const top = [...herbs.value].sort((a, b) => b.count - a.count).slice(0, 12)
  const max = top.reduce((m, h) => Math.max(m, h.count), 1)

  return top.map((h, i) => {
    const angle = i * GOLDEN_ANGLE
    const spread = i === 0 ? 0 : 30 + 39 * Math.sqrt(i)
    const x = 430 + Math.cos(angle) * spread * 1.55
    const y = 150 + Math.sin(angle) * spread * 0.58
    const r = 16 + 22 * (h.count / max)
    const limit = Math.max(2, Math.floor((2 * r - 8) / 10))
    const text = h.herb.length > limit ? `${h.herb.slice(0, limit - 1)}…` : h.herb

    return {
      herb: h.herb,
      count: h.count,
      formulaCount: h.formulaCount,
      x,
      y,
      r,
      color: GALAXY_COLORS[i % GALAXY_COLORS.length],
      text
    }
  })
})

function barWidth(count: number, max: number): string {
  const ratio = max <= 0 ? 0 : (count / max) * 100
  return `${Math.max(count > 0 ? 2 : 0, Math.round(ratio))}%`
}

function pct(ratio: number): string {
  return `${(ratio * 100).toFixed(1)}%`
}

function truncate(text: string, max: number): string {
  return text.length > max ? `${text.slice(0, max)}…` : text
}

function bubbleTitle(b: Bubble): string {
  return `${b.herb} · 出现 ${b.count} 次 · ${b.formulaCount} 方`
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [h, s, t] = await Promise.all([getHerbs(20), getSyndrome(12), getTrend()])
    herbs.value = h
    syndromes.value = s
    trend.value = t
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载失败'
    herbs.value = []
    syndromes.value = []
    trend.value = null
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>
