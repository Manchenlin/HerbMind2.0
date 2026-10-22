<template>
  <div class="crumb">
    <RouterLink to="/">首页</RouterLink> / <RouterLink to="/graph">图谱</RouterLink> / 方心子图
  </div>

  <div style="display:flex;justify-content:space-between;align-items:center;gap:14px;flex-wrap:wrap;margin-bottom:12px">
    <div>
      <h1 class="serif" style="font-size:24px">
        {{ center?.name ?? '未找到该方' }}
        <span class="chip primary" style="font-size:12px;vertical-align:middle">方心子图</span>
      </h1>
      <p class="muted" style="margin-top:4px">
        以本方为中心展开 {{ hops }} 跳：药味 · 主治证候 · 表现症状 · 加减方
      </p>
    </div>
    <span class="pill-tabs">
      <button :class="{ active: hops === 1 }" @click="hops = 1">1 跳</button>
      <button :class="{ active: hops === 2 }" @click="hops = 2">2 跳</button>
    </span>
  </div>

  <p v-if="!center" class="muted" style="color:#A32D2D">
    示意数据里没有 <span class="mono">{{ route.params.id }}</span> 这个方。
    可用：麻黄汤（mahuang）/ 桂枝汤（guizhi）/ 葛根汤（gegen）。
  </p>

  <div v-else class="grid" style="grid-template-columns:1fr 300px;align-items:start">
    <div>
      <div class="card" style="padding:0;overflow:hidden">
        <GraphCanvas :nodes="sub.nodes" :edges="sub.edges" :active-id="cid" @select="openNode" />
      </div>
      <p class="muted" style="margin-top:10px">
        图结构为<b>示意数据</b> · 待 <span class="mono">svc-graph /internal/graph/formula/{id}</span> 落地后替换。
      </p>
    </div>

    <aside style="display:grid;gap:16px">
      <div class="card">
        <h3 style="font-size:15px;margin-bottom:10px">组成（{{ herbs.length }} 味）</h3>
        <div v-if="!herbs.length" class="muted">暂无组成数据。</div>
        <RouterLink
          v-for="h in herbs"
          :key="h.id"
          class="rowitem"
          style="padding:8px 10px;margin-bottom:8px"
          :to="`/ask?q=${encodeURIComponent(`${center?.name} 里的${h.name}起什么作用`)}`"
        >
          <span class="thumb" style="width:30px;height:30px;font-size:12px">{{ h.name.slice(0, 1) }}</span>
          <div><b>{{ h.name }}</b><div class="muted">药味</div></div>
        </RouterLink>
      </div>

      <div class="card">
        <h3 style="font-size:15px;margin-bottom:10px">主治与表现</h3>
        <div style="display:flex;gap:6px;flex-wrap:wrap">
          <span v-for="s in syndromes" :key="s.id" class="chip accent">{{ s.name }}</span>
          <span v-for="s in symptoms" :key="s.id" class="chip">{{ s.name }}</span>
        </div>
        <div class="hr"></div>
        <h3 style="font-size:15px;margin-bottom:8px">加减 / 相似方</h3>
        <div style="display:grid;gap:8px">
          <div v-for="f in related" :key="f.id" class="rowitem" style="padding:8px 10px">
            <span class="thumb" style="width:30px;height:30px;font-size:12px">{{ f.name.slice(0, 1) }}</span>
            <div>
              <b>{{ f.name }}</b>
              <div class="muted">{{ f.relText }}</div>
            </div>
          </div>
          <p v-if="!related.length" class="muted">无</p>
        </div>
      </div>

      <div class="card">
        <h3 style="font-size:15px;margin-bottom:8px">下一步</h3>
        <p class="muted" style="font-size:13px">
          真数据接入后，这里用 <span class="mono">/api/agent/formula/diff</span> 做加减推演（未实现）。
        </p>
        <RouterLink class="btn primary sm" style="margin-top:10px" :to="`/ask?q=${encodeURIComponent(`讲讲${center?.name}的加减法`)}`">
          让 Agent 推演 →
        </RouterLink>
      </div>
    </aside>
  </div>

  <NodeDrawer :open="!!selected" :title="selected?.name ?? ''" @close="selectedId = ''">
    <template v-if="selected">
      <span class="chip" :class="NODE_STYLE[selected.label].cs">{{ NODE_LABEL_CN[selected.label] }}</span>
      <p class="muted" style="margin-top:12px">节点 ID：<span class="mono">{{ selected.id }}</span></p>
      <div class="hr"></div>
      <RouterLink class="btn ghost sm" :to="`/ask?q=${encodeURIComponent(selected.name)}`">就此提问 →</RouterLink>
    </template>
  </NodeDrawer>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import GraphCanvas from '@/components/GraphCanvas.vue'
import NodeDrawer from '@/components/NodeDrawer.vue'
import {
  NODE_LABEL_CN,
  NODE_STYLE,
  REL_CN,
  neighborSubgraph,
  resolveNodeId,
  type GNode
} from '@/mock/domain3'

const route = useRoute()
const hops = ref<1 | 2>(2)
const selectedId = ref('')

const cid = computed(() => resolveNodeId(String(route.params.id)))
const sub = computed(() => neighborSubgraph(cid.value, hops.value))
const center = computed(() => sub.value.center)
const selected = computed(() => sub.value.nodes.find((n) => n.id === selectedId.value) ?? null)

const herbList = (label: GNode['label']) => sub.value.nodes.filter((n) => n.label === label)
const herbs = computed(() => herbList('Herb'))
const syndromes = computed(() => herbList('Syndrome'))
const symptoms = computed(() => herbList('Symptom'))

/** 加减方（MODIFIES）与相似方（SIMILAR_TO）*/
const related = computed(() => {
  const out: Array<{ id: string; name: string; relText: string }> = []
  for (const e of sub.value.edges) {
    const isOut = e.from === cid.value
    const isIn = e.to === cid.value
    if (!isOut && !isIn) continue
    if (e.rel !== 'MODIFIES' && e.rel !== 'SIMILAR_TO') continue
    const otherId = isOut ? e.to : e.from
    const n = sub.value.nodes.find((x) => x.id === otherId)
    if (n) out.push({ id: n.id, name: n.name, relText: REL_CN[e.rel] })
  }
  return out
})

function openNode(id: string) {
  selectedId.value = id
}
</script>
