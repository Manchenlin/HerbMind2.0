<template>
  <div class="crumb"><RouterLink to="/">首页</RouterLink> / 图谱</div>

  <div style="display:flex;justify-content:space-between;align-items:center;gap:14px;flex-wrap:wrap;margin-bottom:12px">
    <div>
      <h1 class="serif" style="font-size:24px">知识图谱探索</h1>
      <p class="muted" style="margin-top:4px">
        以「麻黄汤」为中心的 1~2 跳邻居子图 · 节点 {{ shownNodes.length }} 个 / 关系 {{ shownEdges.length }} 条
      </p>
    </div>
    <RouterLink class="chip clickable" to="/graph/map">方证相似度地图 →</RouterLink>
  </div>

  <!-- 真实连接状态：Neo4j 规模来自 /api/agent/health，不是示意数据 -->
  <div class="card" style="padding:12px 16px;margin-bottom:14px;display:flex;gap:10px;align-items:center;flex-wrap:wrap">
    <span class="badge" :class="healthState.cls">{{ healthState.text }}</span>
    <span class="muted" v-if="healthState.detail">{{ healthState.detail }}</span>
    <span class="spacer" style="flex:1"></span>
    <span class="muted" style="font-size:12.5px">
      图结构为<b>示意数据</b> · 待 <span class="mono">svc-graph</span> 的
      <span class="mono">/internal/graph/neighbors</span> 落地后替换
    </span>
  </div>

  <div class="card" style="margin-bottom:14px;display:flex;gap:8px;flex-wrap:wrap;align-items:center">
    <span class="muted" style="margin-right:6px">筛选：</span>
    <button
      v-for="t in TYPES"
      :key="t.text"
      class="chip clickable"
      :class="{ sel: enabled.has(t.label) && !t.disabled }"
      :style="t.disabled ? 'opacity:.45;cursor:not-allowed' : ''"
      :title="t.disabled ? '该类型暂无数据（待接入真图）' : ''"
      @click="toggle(t.label, t.disabled)"
    >{{ t.text }}</button>
    <span class="spacer" style="flex:1"></span>
    <button class="btn ghost sm" @click="relayout">重新布局</button>
  </div>

  <div class="card" style="padding:0;overflow:hidden">
    <GraphCanvas :nodes="shownNodes" :edges="shownEdges" :active-id="selectedId" @select="openNode" />
  </div>

  <p class="muted" style="margin-top:10px">
    提示：点击节点查看详情；悬停可高亮邻居。当前为「麻黄汤」子图（示意）。
  </p>

  <NodeDrawer :open="!!selected" :title="selected?.name ?? ''" @close="selectedId = ''">
    <template v-if="selected">
      <span class="chip" :class="NODE_STYLE[selected.label].cs">{{ NODE_LABEL_CN[selected.label] }}</span>
      <p class="muted" style="margin-top:12px">
        节点 ID：<span class="mono">{{ selected.id }}</span><br />
        连接关系：{{ selectedRels.length }} 条
      </p>

      <div class="hr"></div>
      <div style="display:grid;gap:8px">
        <div v-for="(r, i) in selectedRels" :key="i" class="rowitem" style="padding:8px 10px">
          <span class="thumb" style="width:30px;height:30px;font-size:12px">{{ r.other.name.slice(0, 1) }}</span>
          <div>
            <div style="font-size:13.5px">
              <b>{{ r.other.name }}</b>
              <span class="muted"> · {{ r.relText }}</span>
            </div>
            <div class="muted" style="font-size:12px">{{ NODE_LABEL_CN[r.other.label] }}</div>
          </div>
        </div>
      </div>

      <div class="hr"></div>
      <div style="display:flex;gap:8px;flex-wrap:wrap">
        <RouterLink
          v-if="selected.label === 'Formula'"
          class="btn primary sm"
          :to="`/graph/formula/${selected.id}`"
        >方心子图 →</RouterLink>
        <RouterLink class="btn ghost sm" :to="`/ask?q=${encodeURIComponent(selected.name)}`">就此提问 →</RouterLink>
      </div>
    </template>
  </NodeDrawer>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import GraphCanvas from '@/components/GraphCanvas.vue'
import NodeDrawer from '@/components/NodeDrawer.vue'
import { errMsg, getHealth } from '@/api/agent'
import {
  DEMO_GRAPH,
  NODE_LABEL_CN,
  NODE_STYLE,
  REL_CN,
  type GNode,
  type NodeLabel
} from '@/mock/domain3'

const TYPES: Array<{ label: NodeLabel; text: string; disabled?: boolean }> = [
  { label: 'Formula', text: '方剂' },
  { label: 'Herb', text: '药味' },
  { label: 'Syndrome', text: '证候' },
  { label: 'Symptom', text: '症状' },
  { label: 'Formula', text: '条文', disabled: true },
  { label: 'Formula', text: '经典', disabled: true }
]

const enabled = ref(new Set<NodeLabel>(['Formula', 'Herb', 'Syndrome', 'Symptom']))
const selectedId = ref('')
const jitter = ref(0)

function toggle(label: NodeLabel, disabled?: boolean) {
  if (disabled) return
  const next = new Set(enabled.value)
  if (next.has(label)) next.delete(label)
  else next.add(label)
  enabled.value = next
}

/** 轻微抖动重排：中心不动，外围节点换个角度，用来直观看出"布局可调" */
function relayout() {
  jitter.value += 1
}

const layoutNodes = computed<GNode[]>(() =>
  DEMO_GRAPH.nodes.map((n, i) => {
    if (n.id === 'mahuang' || !jitter.value) return n
    const seed = Math.sin((i + 1) * 12.9898 + jitter.value * 78.233) * 43758.5453
    const frac = seed - Math.floor(seed)
    const ang = frac * Math.PI * 2
    const dist = 26 + ((i * 7 + jitter.value * 13) % 34)
    return {
      ...n,
      x: Math.round(Math.max(60, Math.min(800, n.x + Math.cos(ang) * dist))),
      y: Math.round(Math.max(60, Math.min(500, n.y + Math.sin(ang) * dist)))
    }
  })
)

const shownNodes = computed(() => layoutNodes.value.filter((n) => enabled.value.has(n.label)))
const shownIds = computed(() => new Set(shownNodes.value.map((n) => n.id)))
const shownEdges = computed(() =>
  DEMO_GRAPH.edges.filter((e) => shownIds.value.has(e.from) && shownIds.value.has(e.to))
)

const selected = computed(() => shownNodes.value.find((n) => n.id === selectedId.value) ?? null)

const selectedRels = computed(() => {
  const cur = selected.value
  if (!cur) return []
  const out: Array<{ relText: string; other: GNode }> = []
  for (const e of DEMO_GRAPH.edges) {
    const otherId = e.from === cur.id ? e.to : e.to === cur.id ? e.from : ''
    if (!otherId) continue
    const other = DEMO_GRAPH.nodes.find((n) => n.id === otherId)
    if (other) out.push({ relText: REL_CN[e.rel], other })
  }
  return out
})

function openNode(id: string) {
  selectedId.value = id
}

/* ---- health：给页面一个"真的连上了吗"的锚点 ---- */
const health = ref<Awaited<ReturnType<typeof getHealth>> | null>(null)
const healthError = ref('')

const healthState = computed(() => {
  if (healthError.value) return { cls: 'err', text: 'Agent 未连上', detail: healthError.value }
  if (!health.value) return { cls: 'info', text: '探测中…', detail: '' }
  const neo = health.value.deps?.neo4j
  if (!neo) return { cls: 'warn', text: '无 Neo4j 探测结果', detail: '' }
  return {
    cls: neo.ok ? 'ok' : 'warn',
    text: neo.ok ? `Neo4j 在线 · ${neo.latencyMs}ms` : 'Neo4j 异常',
    detail: neo.detail
  }
})

onMounted(async () => {
  try {
    health.value = await getHealth()
  } catch (e) {
    healthError.value = errMsg(e, '请确认网关 :8080 与 Agent :8091 已启动')
  }
})
</script>
