<template>
  <div class="crumb">
    <RouterLink to="/">首页</RouterLink> / <RouterLink to="/graph">图谱</RouterLink> / 方心子图
  </div>

  <div style="display:flex;justify-content:space-between;align-items:center;gap:14px;flex-wrap:wrap;margin-bottom:12px">
    <div>
      <h1 class="serif" style="font-size:24px">
        {{ data?.center.name ?? '查询中…' }}
        <span class="chip primary" style="font-size:12px;vertical-align:middle">方心子图</span>
      </h1>
      <p class="muted" style="margin-top:4px">
        以本方为中心：药味 {{ data?.herbs.length ?? 0 }} 味 · 组成相近的方 {{ data?.relatedFormulas.length ?? 0 }} 首
        <span v-if="data?.center.alias"> · 别名「{{ data.center.alias }}」</span>
      </p>
    </div>
    <RouterLink class="chip clickable" to="/graph">← 返回图谱</RouterLink>
  </div>

  <div v-if="loading" class="card muted" style="padding:16px;margin-bottom:12px">正在加载方剂「{{ route.params.id }}」…</div>

  <div v-if="error" class="card" style="padding:12px 16px;margin-bottom:12px;border-left:3px solid #A32D2D">
    <b style="color:#A32D2D">没查到这首方</b>
    <p class="muted" style="margin-top:6px">{{ error }}</p>
    <p class="muted" style="margin-top:6px">
      可以改用方剂 ID（如 <span class="mono">f_1</span>），或从
      <RouterLink to="/graph" style="color:#2E7D6F">图谱探索</RouterLink> 里点一个方剂进来。
    </p>
  </div>

  <div v-if="data" class="grid" style="grid-template-columns:1fr 320px;align-items:start">
    <div>
      <div v-if="data.herbsIncomplete" class="card" style="padding:10px 14px;margin-bottom:10px;background:#FBEDE7">
        <b style="color:#B4552F">提示：本方在库内药味可能不完整</b>
        <p class="muted" style="margin-top:4px;font-size:12.5px">
          存在缺失或疑似解析残留（脏药名）。图与列表都按库内现有记录展示，未做补全。
        </p>
      </div>
      <div class="card" style="padding:0;overflow:hidden">
        <GraphCanvas :nodes="graph.nodes" :edges="graph.edges" :active-id="selectedId" @select="openNode" />
      </div>
      <p class="muted" style="margin-top:10px">
        数据来源：<span class="mono">svc-graph /internal/graph/formula/{id}</span>
        （中心方与药味顺序取自 PG，图为 Neo4j 组成关系）。
      </p>
    </div>

    <aside style="display:grid;gap:16px">
      <div class="card">
        <h3 style="font-size:15px;margin-bottom:10px">组成（{{ data.herbs.length }} 味，按库内顺序）</h3>
        <div v-if="!data.herbs.length" class="muted">库内暂无该方药味记录。</div>
        <RouterLink
          v-for="h in data.herbs"
          :key="h.id"
          class="rowitem"
          style="padding:8px 10px;margin-bottom:8px"
          :to="`/ask?q=${encodeURIComponent(`${data.center.name} 里的${h.name}起什么作用`)}`"
        >
          <span class="thumb" style="width:30px;height:30px;font-size:12px">{{ h.seq }}</span>
          <div>
            <b>{{ h.name }}</b>
            <div class="muted">
              {{ h.dose ? `${h.dose}${h.unit ?? ''}` : '库内未记剂量' }}
              <span v-if="h.role"> · {{ h.role }}</span>
            </div>
          </div>
        </RouterLink>
      </div>

      <div class="card">
        <h3 style="font-size:15px;margin-bottom:8px">主治（证候原文）</h3>
        <p v-if="data.center.syndromeText" class="muted" style="font-size:13px;line-height:1.8">
          {{ data.center.syndromeText }}
        </p>
        <p v-else class="muted">库内未记录该方证候原文。</p>
        <p class="muted" style="margin-top:8px;font-size:12px">
          以上为语料原文摘录，未做推断或改写。
        </p>
      </div>

      <div class="card">
        <h3 style="font-size:15px;margin-bottom:8px">组成相近的方（按药味重合度）</h3>
        <div style="display:grid;gap:8px">
          <RouterLink
            v-for="f in data.relatedFormulas"
            :key="f.id"
            class="rowitem"
            style="padding:8px 10px"
            :to="`/graph/formula/${encodeURIComponent(f.id)}`"
          >
            <span class="thumb" style="width:30px;height:30px;font-size:12px">{{ f.name.slice(0, 1) }}</span>
            <div>
              <b>{{ f.name }}</b>
              <div class="muted">共有 {{ f.sharedHerbs.join('、') || '—' }}</div>
              <div class="muted" style="font-size:12px">
                Jaccard {{ typeof f.jaccard === 'number' ? f.jaccard.toFixed(4) : '—' }}
              </div>
            </div>
          </RouterLink>
          <p v-if="!data.relatedFormulas.length" class="muted">库内没有组成相近的方。</p>
        </div>
        <p class="muted" style="margin-top:8px;font-size:12px">
          仅表示药味集合重合度：<b>组成相近 ≠ 同一方</b>，不代表功效相同或可互相替代。
        </p>
      </div>

      <div class="card">
        <h3 style="font-size:15px;margin-bottom:8px">下一步</h3>
        <div style="display:flex;gap:8px;flex-wrap:wrap">
          <RouterLink
            class="btn primary sm"
            :to="`/ask?q=${encodeURIComponent(`讲讲${data.center.name}的加减法`)}`"
          >让 Agent 查证加减 →</RouterLink>
          <RouterLink class="btn ghost sm" :to="`/graph`">回到图谱</RouterLink>
        </div>
      </div>
    </aside>
  </div>

  <p v-if="data" class="muted" style="margin-top:14px;font-size:12.5px">{{ data.notice }}</p>

  <NodeDrawer :open="!!selected" :title="selected?.name ?? ''" @close="selectedId = ''">
    <template v-if="selected">
      <span class="chip" :class="NODE_STYLE[selected.label].cs">{{ NODE_LABEL_CN[selected.label] }}</span>
      <p class="muted" style="margin-top:12px">节点 ID：<span class="mono">{{ selected.id }}</span></p>
      <div class="hr"></div>
      <div style="display:flex;gap:8px;flex-wrap:wrap">
        <RouterLink class="btn ghost sm" :to="`/ask?q=${encodeURIComponent(selected.name)}`">就此提问 →</RouterLink>
      </div>
    </template>
  </NodeDrawer>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import GraphCanvas from '@/components/GraphCanvas.vue'
import NodeDrawer from '@/components/NodeDrawer.vue'
import { getGraphFormula, graphErrMsg, type FormulaGraphVO } from '@/api/graph'
import { NODE_LABEL_CN, NODE_STYLE, type GNode } from '@/mock/domain3'
import { layoutFormula } from '@/utils/graphLayout'

/**
 * 方心子图页 —— 数据来自 `/api/biz/graph/formula/{idOrName}`。
 *
 * 与旧示意数据的差别：库里**没有**证候/症状节点，也没有 MODIFIES / SIMILAR_TO 关系。
 * 所以这一页展示的是「中心方 + 药味（真实组成关系）+ 组成相近的方（Jaccard 计算）」，
 * 相关方在图上是孤立点、不造假边 —— 否则会让人以为库里真有「加减/相似」关系。
 */
const route = useRoute()
const data = ref<FormulaGraphVO | null>(null)
const loading = ref(false)
const error = ref('')
const selectedId = ref('')

const graph = computed(() =>
  data.value ? layoutFormula(data.value) : { nodes: [] as GNode[], edges: [] }
)

const selected = computed(() => graph.value.nodes.find((n) => n.id === selectedId.value) ?? null)

async function load(idOrName: string) {
  if (!idOrName) return
  loading.value = true
  error.value = ''
  data.value = null
  selectedId.value = ''
  try {
    data.value = await getGraphFormula(idOrName)
  } catch (e) {
    error.value = graphErrMsg(e)
  } finally {
    loading.value = false
  }
}

function openNode(id: string) {
  selectedId.value = id
}

// 同一页内切换方剂（点"组成相近的方"）时路由参数会变，必须跟着重新取数。
// immediate 已经覆盖首次加载，不要再加 onMounted，否则同一路由会请求两次。
watch(() => route.params.id, (v) => load(String(v ?? '')), { immediate: true })
</script>
