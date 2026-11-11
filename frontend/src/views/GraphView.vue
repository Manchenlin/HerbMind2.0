<template>
  <div class="crumb"><RouterLink to="/">首页</RouterLink> / 图谱</div>

  <div style="display:flex;justify-content:space-between;align-items:center;gap:14px;flex-wrap:wrap;margin-bottom:12px">
    <div>
      <h1 class="serif" style="font-size:24px">知识图谱探索</h1>
      <p class="muted" style="margin-top:4px">
        以「{{ data?.center.name ?? entity }}」为中心的 1 跳邻居 · 节点 {{ shownNodes.length }} 个 / 关系 {{ shownEdges.length }} 条
      </p>
    </div>
    <RouterLink class="chip clickable" to="/graph/map">方证相似度地图 →</RouterLink>
  </div>

  <!-- 查询：后端 /api/biz/graph/neighbors 支持方名、方剂 ID(f_1)、药名、药味 ID(h_麻黄) -->
  <div class="card" style="padding:12px 16px;margin-bottom:12px;display:flex;gap:10px;align-items:center;flex-wrap:wrap">
    <input
      v-model="keyword"
      class="input"
      style="flex:1;min-width:220px"
      placeholder="输入方名 / 药名 / ID，如 麻黄汤、桂枝、f_1、h_麻黄"
      @keyup.enter="load(keyword)"
    />
    <button class="btn primary sm" :disabled="loading" @click="load(keyword)">
      {{ loading ? '查询中…' : '查询邻居' }}
    </button>
    <span class="spacer" style="flex:1"></span>
    <button
      v-for="s in SHORTCUTS"
      :key="s"
      class="chip clickable"
      :class="{ sel: entity === s }"
      @click="load(s)"
    >{{ s }}</button>
  </div>

  <div v-if="error" class="card" style="padding:12px 16px;margin-bottom:12px;border-left:3px solid #A32D2D">
    <b style="color:#A32D2D">图谱查询失败</b>
    <p class="muted" style="margin-top:6px">{{ error }}</p>
  </div>

  <div class="card" style="margin-bottom:14px;display:flex;gap:8px;flex-wrap:wrap;align-items:center">
    <span class="muted" style="margin-right:6px">显示：</span>
    <button
      v-for="t in TYPES"
      :key="t.label"
      class="chip clickable"
      :class="{ sel: enabled.has(t.label) }"
      @click="toggle(t.label)"
    >{{ t.text }}</button>
    <span class="spacer" style="flex:1"></span>
    <span v-if="data?.truncated" class="chip" style="background:#FBEDE7;color:#B4552F">
      邻居超过上限，仅显示前 {{ data.nodes.length }} 个
    </span>
  </div>

  <div class="card" style="padding:0;overflow:hidden">
    <GraphCanvas :nodes="shownNodes" :edges="shownEdges" :active-id="selectedId" @select="openNode" />
  </div>

  <p class="muted" style="margin-top:10px">
    数据来源：<span class="mono">svc-graph</span> → Neo4j（节点 {{ data?.nodes.length ?? 0 }} 个邻居，含中心）。
    点击节点查看详情；悬停高亮其邻居。
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
          :to="`/graph/formula/${encodeURIComponent(selected.id)}`"
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
import {
  getGraphNeighbors,
  graphErrMsg,
  isEntityMissing,
  type GraphLabel,
  type NeighborsVO
} from '@/api/graph'
import { NODE_LABEL_CN, NODE_STYLE, REL_CN, type GEdge, type GNode, type NodeLabel } from '@/mock/domain3'
import { layoutNeighbors } from '@/utils/graphLayout'

/**
 * 图谱探索页 —— 数据来自 `/api/biz/graph/neighbors`（BFF → svc-graph → Neo4j）。
 *
 * 库里目前只有 Formula / Herb 两类节点，所以筛选只给这两类；
 * 证候 / 症状尚未实体化，页面上不摆点了没有数据的按钮。
 */
const TYPES: Array<{ label: NodeLabel; text: string }> = [
  { label: 'Formula', text: '方剂' },
  { label: 'Herb', text: '药味' }
]

/** 快捷入口：都是库里确有的实体，避免用户瞎猜导致 404 */
const SHORTCUTS = ['麻黄汤', '桂枝汤', '葛根汤', '麻黄', '桂枝']

const keyword = ref('麻黄汤')
const entity = ref('麻黄汤')
const data = ref<NeighborsVO | null>(null)
const loading = ref(false)
const error = ref('')
const enabled = ref(new Set<NodeLabel>(['Formula', 'Herb']))
const selectedId = ref('')

/** 带业务 ID 前缀时直接定类型；中文名交给「先方后药」的兜底 */
function guessLabel(q: string): GraphLabel | undefined {
  if (/^h[_:]/.test(q)) return 'Herb'
  if (/^f[_:]/.test(q)) return 'Formula'
  return undefined
}

/**
 * 按「方剂 → 药味」顺序查一次。
 *
 * 契约 §15.1 的 `label` 默认值是 `Formula`，所以用户输入中文药名（桂枝）会先拿到
 * 4040「图中找不到实体」——那不是真没有，是类型没给对。这里在 404 且带后端 msg
 * （`isEntityMissing`）时按 `Herb` 再查一次；两个都没有才如实报错。
 */
async function queryNeighbors(q: string): Promise<NeighborsVO> {
  const label = guessLabel(q)
  if (label) return getGraphNeighbors({ entity: q, label, hops: 1, limit: 50 })
  try {
    return await getGraphNeighbors({ entity: q, hops: 1, limit: 50 })
  } catch (e) {
    if (!isEntityMissing(e)) throw e
    try {
      return await getGraphNeighbors({ entity: q, label: 'Herb', hops: 1, limit: 50 })
    } catch (herbErr) {
      if (!isEntityMissing(herbErr)) throw herbErr
      // 两个类型都查过才下"不存在"的结论：保留服务端原文，只在后面补一句已试过的范围，
      // 不要用自造字符串覆盖掉原始 msg。
      throw new Error(`${graphErrMsg(herbErr)}（已按方剂、药味各查一次）`)
    }
  }
}

/** 请求序号：只让最后一次查询的结果落地，避免慢请求覆盖新结果 */
let loadSeq = 0

async function load(name: string) {
  const q = name.trim()
  if (!q) return
  const seq = ++loadSeq
  loading.value = true
  error.value = ''
  try {
    const result = await queryNeighbors(q)
    if (seq !== loadSeq) return
    data.value = result
    entity.value = q
    selectedId.value = ''
  } catch (e) {
    if (seq !== loadSeq) return
    data.value = null
    error.value = graphErrMsg(e)
  } finally {
    if (seq === loadSeq) loading.value = false
  }
}

function toggle(label: NodeLabel) {
  const next = new Set(enabled.value)
  if (next.has(label) && next.size > 1) next.delete(label)
  else next.add(label)
  enabled.value = next
}

const layout = computed(() =>
  data.value ? layoutNeighbors(data.value) : { nodes: [] as GNode[], edges: [] as GEdge[] }
)

const shownNodes = computed(() => layout.value.nodes.filter((n) => enabled.value.has(n.label)))
const shownIds = computed(() => new Set(shownNodes.value.map((n) => n.id)))
const shownEdges = computed(() =>
  layout.value.edges.filter((e) => shownIds.value.has(e.from) && shownIds.value.has(e.to))
)

const selected = computed(() => shownNodes.value.find((n) => n.id === selectedId.value) ?? null)

const selectedRels = computed(() => {
  const cur = selected.value
  if (!cur) return []
  const out: Array<{ relText: string; other: GNode }> = []
  for (const e of shownEdges.value) {
    const otherId = e.from === cur.id ? e.to : e.to === cur.id ? e.from : ''
    if (!otherId) continue
    const other = shownNodes.value.find((n) => n.id === otherId)
    if (other) out.push({ relText: REL_CN[e.rel], other })
  }
  return out
})

function openNode(id: string) {
  selectedId.value = id
}

onMounted(() => load(entity.value))
</script>
