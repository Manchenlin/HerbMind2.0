<template>
  <div class="crumb">
    <RouterLink to="/">首页</RouterLink> /
    <RouterLink to="/research">科研</RouterLink> /
    数据导出
  </div>

  <div
    style="display:flex;justify-content:space-between;align-items:flex-end;gap:18px;flex-wrap:wrap;margin-bottom:18px"
  >
    <div>
      <h1 class="serif" style="font-size:26px">数据导出</h1>
      <p class="muted" style="margin-top:4px">
        按需导出 CSV/JSON；研究包附带 seed 与数据指纹，保证可复现。
      </p>
    </div>
    <RouterLink class="chip clickable" to="/research">← 返回科研工作台</RouterLink>
  </div>

  <div class="grid cols-2">
    <!-- 快速导出 -->
    <section class="card" style="align-self:start">
      <h3>快速导出</h3>
      <p class="muted" style="margin-top:2px">直接下载当前数据快照，适合快速取数或做表。</p>

      <div class="field" style="margin-top:16px">
        <label>数据表</label>
        <div style="display:flex;gap:8px;flex-wrap:wrap">
          <button
            v-for="k in kinds"
            :key="k.value"
            type="button"
            class="chip clickable"
            :class="{ sel: kind === k.value }"
            @click="selectKind(k.value)"
          >{{ k.label }}</button>
        </div>
      </div>

      <div class="field">
        <label>格式</label>
        <span class="pill-tabs">
          <button
            v-for="f in formats"
            :key="f"
            type="button"
            :class="{ active: format === f }"
            @click="setFormat(f)"
          >{{ f.toUpperCase() }}</button>
        </span>
      </div>

      <button class="btn primary" type="button" @click="download">↓ 下载</button>

      <div class="hr"></div>
      <div class="muted" style="font-weight:700;color:var(--text);margin-bottom:4px">各表字段</div>
      <div
        v-for="k in kinds"
        :key="`note-${k.value}`"
        style="padding:9px 0;border-bottom:1px solid var(--border)"
      >
        <div style="display:flex;align-items:center;gap:8px">
          <b style="font-size:13.5px">{{ k.label }}</b>
          <span class="mono muted" style="font-size:12px">{{ k.value }}</span>
        </div>
        <div class="muted" style="font-size:12.5px">{{ k.fields }}</div>
      </div>
    </section>

    <!-- 可复现研究包 -->
    <section class="card" style="align-self:start">
      <h3>可复现研究包</h3>
      <p class="muted" style="margin-top:2px">
        固定 seed 与数据指纹，便于复现同一份统计结果。
      </p>

      <div class="grid cols-2" style="gap:12px;margin-top:16px">
        <div class="field" style="margin-bottom:0">
          <label for="pack-topn">Top N</label>
          <input
            id="pack-topn"
            v-model.number="topN"
            class="input"
            type="number"
            min="1"
            max="100"
            step="1"
          />
        </div>
        <div class="field" style="margin-bottom:0">
          <label for="pack-seed">Seed（留空 = 当天）</label>
          <input
            id="pack-seed"
            v-model="seed"
            class="input"
            type="text"
            placeholder="如 20261027"
          />
        </div>
      </div>

      <div class="field" style="margin-top:12px">
        <label for="pack-scope">数据范围</label>
        <select id="pack-scope" v-model="scope" class="input">
          <option v-for="s in scopes" :key="s.value" :value="s.value">{{ s.label }}</option>
        </select>
      </div>

      <button
        class="btn primary"
        type="button"
        :disabled="generating"
        :style="generating ? 'opacity:.65;cursor:wait' : ''"
        @click="generate"
      >
        <span
          v-if="generating"
          class="spin"
          style="border-color:rgba(255,255,255,.35);border-top-color:#fff"
        ></span>
        {{ generating ? '生成中…' : '生成研究包' }}
      </button>

      <div
        v-if="error"
        style="margin-top:14px;padding:12px 14px;border:1px solid #F0D5C9;background:var(--error-soft);color:var(--error);border-radius:var(--radius);font-size:13.5px"
      >
        <b>生成失败：</b>{{ error }}
      </div>

      <p
        v-else-if="generating && !pack"
        class="muted"
        style="margin-top:16px;padding:16px;border:1px dashed var(--border-strong);border-radius:var(--radius);text-align:center"
      >
        正在生成研究包，请稍候…
      </p>

      <p
        v-else-if="!pack"
        class="muted"
        style="margin-top:16px;padding:16px;border:1px dashed var(--border-strong);border-radius:var(--radius);text-align:center"
      >
        尚未生成研究包。设置参数后点击「生成研究包」。
      </p>

      <template v-if="pack">
        <div class="hr"></div>
        <div
          style="display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap"
        >
          <div>
            <div class="muted" style="font-size:12.5px">packId</div>
            <div class="mono" style="font-weight:700;color:var(--primary-deep)">
              {{ pack.packId }}
            </div>
          </div>
          <span class="badge ok">已生成</span>
        </div>

        <div class="grid cols-2" style="gap:10px 16px;margin-top:12px">
          <div>
            <div class="muted" style="font-size:12.5px">生成时间</div>
            <div style="font-size:13.5px">{{ formatTime(pack.generatedAt) }}</div>
          </div>
          <div>
            <div class="muted" style="font-size:12.5px">seed</div>
            <div class="mono" style="font-size:13.5px">{{ pack.seed }}</div>
          </div>
        </div>

        <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:14px">
          <button class="btn primary sm" type="button" @click="downloadJson">↓ 下载 JSON</button>
          <button class="btn ghost sm" type="button" @click="copySummary">复制摘要</button>
        </div>

        <div class="muted" style="margin:14px 0 6px;font-weight:700;color:var(--text)">摘要</div>
        <table class="tb" style="font-size:13px">
          <tbody>
            <tr v-for="row in summaryRows" :key="row.key">
              <td style="color:var(--text-2)">{{ row.label }}</td>
              <td class="mono" style="text-align:right">{{ row.value }}</td>
            </tr>
          </tbody>
        </table>

        <div class="muted" style="margin:14px 0 6px;font-weight:700;color:var(--text)">数据表</div>
        <div
          v-for="t in pack.tables"
          :key="t.name"
          style="display:flex;align-items:center;justify-content:space-between;gap:10px;padding:8px 0;border-bottom:1px solid var(--border)"
        >
          <div>
            <b style="font-size:13.5px">{{ t.title }}</b>
            <span class="mono muted" style="font-size:12px;margin-left:8px">{{ t.name }}</span>
          </div>
          <span class="chip">{{ t.rows.length }} 行</span>
        </div>

        <div class="muted" style="margin:14px 0 6px;font-weight:700;color:var(--text)">文件清单</div>
        <ol style="margin:4px 0 0 20px;font-size:13px;color:var(--text-2)">
          <li v-for="f in pack.files" :key="f" style="margin-bottom:2px">{{ f }}</li>
        </ol>
      </template>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { createResearchPack, exportUrl, type ResearchPack } from '@/api/insight'
import { toast } from '@/utils/toast'

type ExportFormat = 'csv' | 'json'
type KindValue = 'herbs' | 'formulas' | 'quotes' | 'units'

interface KindOption {
  value: KindValue
  label: string
  fields: string
}

const kinds: KindOption[] = [
  {
    value: 'herbs',
    label: '用药频次',
    fields: 'herb 药名 · count 出现次数 · formulaCount 涉及方剂数 · ratio 方剂占比'
  },
  {
    value: 'formulas',
    label: '方剂与药味',
    fields: 'id 方剂 ID · name 方名 · efficacy 功效 · syndrome 主治 · page 页码 · herbs 组成'
  },
  {
    value: 'quotes',
    label: '条文原文',
    fields: 'id 条文 ID · classic 经典 · articleNo 条号 · page 页码 · content 原文'
  },
  {
    value: 'units',
    label: '内容单元',
    fields: 'id 单元 ID · book 典籍 · unitType 单元类型 · refType/refId 关联对象 · title 标题'
  }
]

const formats: ExportFormat[] = ['csv', 'json']

const scopes = [
  { value: 'all', label: '全部语料' },
  { value: 'book:bk_1', label: '《伤寒论》' },
  { value: 'book:bk_2', label: '《温病学》' },
  { value: 'book:bk_3', label: '《金匮要略》' }
]

const kind = ref<KindValue>('herbs')
const format = ref<ExportFormat>('csv')

const topN = ref<number | string>(20)
const seed = ref('')
const scope = ref('all')

const generating = ref(false)
const error = ref('')
const pack = ref<ResearchPack | null>(null)

const currentKind = computed<KindOption>(
  () => kinds.find((k) => k.value === kind.value) ?? kinds[0]
)

const SUMMARY_LABELS: Record<string, string> = {
  formulas: '方剂数',
  cases: '医案数',
  quotes: '条文数',
  contentUnits: '内容单元',
  vectors: '向量化单元',
  dataFingerprint: '数据指纹',
  totalHerbs: '药味种数'
}

const summaryRows = computed(() => {
  const p = pack.value
  if (!p) return []
  return Object.entries(p.summary).map(([key, value]) => ({
    key,
    label: SUMMARY_LABELS[key] ?? key,
    value: String(value)
  }))
})

function selectKind(value: KindValue) {
  kind.value = value
}

function setFormat(value: ExportFormat) {
  format.value = value
}

function download() {
  const k = currentKind.value
  const a = document.createElement('a')
  a.href = exportUrl(k.value, format.value)
  a.download = `herbmind-${k.value}.${format.value}`
  a.rel = 'noopener'
  document.body.appendChild(a)
  a.click()
  a.remove()
  toast(`已开始下载：${k.label} · ${format.value.toUpperCase()}`)
}

function formatTime(value: string): string {
  const d = new Date(value)
  return Number.isNaN(d.getTime()) ? value : d.toLocaleString('zh-CN', { hour12: false })
}

async function generate() {
  if (generating.value) return
  generating.value = true
  error.value = ''
  pack.value = null
  try {
    const n = Number(topN.value)
    if (!Number.isFinite(n) || n < 1 || n > 100) {
      throw new Error('Top N 需为 1–100 的整数')
    }
    const seedText = seed.value.trim()
    const params: Record<string, unknown> = {
      topN: Math.trunc(n),
      scope: scope.value
    }
    if (seedText) {
      params.seed = seedText
    }
    pack.value = await createResearchPack(params)
    toast('研究包已生成')
  } catch (e) {
    error.value = e instanceof Error ? e.message : '生成失败'
    toast(error.value)
  } finally {
    generating.value = false
  }
}

function downloadJson() {
  const p = pack.value
  if (!p) return
  const blob = new Blob([JSON.stringify(p, null, 2)], { type: 'application/json;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `herbmind-research-pack-${p.packId}.json`
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
  toast('研究包 JSON 已开始下载')
}

async function copySummary() {
  const p = pack.value
  if (!p) return
  const lines = [
    `HerbMind 可复现研究包 ${p.packId}`,
    `生成时间：${formatTime(p.generatedAt)}`,
    `seed：${p.seed}`,
    '',
    '摘要',
    ...Object.entries(p.summary).map(([key, value]) => `- ${SUMMARY_LABELS[key] ?? key}：${value}`),
    '',
    `数据表：${p.tables.map((t) => `${t.title}（${t.rows.length} 行）`).join('；')}`,
    `文件：${p.files.join('；')}`
  ]
  try {
    await navigator.clipboard.writeText(lines.join('\n'))
    toast('摘要已复制')
  } catch {
    toast('复制失败，请手动选择页面中的摘要文本')
  }
}
</script>
