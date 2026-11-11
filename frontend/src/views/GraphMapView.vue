<template>
  <div class="crumb">
    <RouterLink to="/">首页</RouterLink> / <RouterLink to="/graph">图谱</RouterLink> / 相似度地图
  </div>

  <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:14px;flex-wrap:wrap;margin-bottom:12px">
    <div>
      <h1 class="serif" style="font-size:24px">方证相似度地图</h1>
      <p class="muted" style="margin-top:4px">
        全部方剂按<b>药味组成重合度</b>（Jaccard）降维投影到 2D：距离越近，共用药味越多。
        当前 {{ points.length }} 首方 · {{ groups.length }} 个分组
        <span v-if="data?.truncated">（已达上限，仅显示前 {{ points.length }} 首）</span>
      </p>
    </div>
    <div style="display:flex;gap:8px;align-items:center">
      <select v-model.number="limit" class="input" style="width:110px" @change="load">
        <option :value="60">60 首</option>
        <option :value="150">150 首</option>
        <option :value="250">250 首</option>
      </select>
      <RouterLink class="chip clickable" to="/graph">← 返回图谱</RouterLink>
    </div>
  </div>

  <div v-if="error" class="card" style="padding:12px 16px;margin-bottom:12px;border-left:3px solid #A32D2D">
    <b style="color:#A32D2D">地图数据加载失败</b>
    <p class="muted" style="margin-top:6px">{{ error }}</p>
  </div>

  <div v-if="loading" class="card muted" style="padding:16px;margin-bottom:12px">
    正在计算 {{ limit }} 首方的药味重合度与二维坐标…
  </div>

  <div v-if="points.length" class="card" style="padding:0;overflow:hidden">
    <svg
      :viewBox="`0 0 ${CANVAS_W} ${CANVAS_H}`"
      style="width:100%;max-height:66vh;display:block;background:radial-gradient(circle at 40% 40%,#FBFCFB,#EFF3F1)"
      @mouseleave="hoverId = ''"
    >
      <g
        v-for="(p, i) in points"
        :key="p.id"
        class="bubble-node"
        :style="{ animationDelay: `${Math.min(i * 8, 320)}ms` }"
        @mouseenter="hoverId = p.id"
        @click="open(p)"
      >
        <circle
          :cx="p.x"
          :cy="p.y"
          :r="hoverId === p.id ? p.r * 1.6 : p.r"
          :fill="`${colorOf(p.cluster)}22`"
          :stroke="colorOf(p.cluster)"
          :stroke-width="hoverId === p.id ? 2.4 : 1.4"
        />
        <text
          v-if="hoverId === p.id"
          :x="p.x"
          :y="p.y - p.r - 8"
          text-anchor="middle"
          font-size="12"
          fill="#1F2328"
          pointer-events="none"
        >{{ p.name }}</text>
        <title>{{ p.name }}</title>
      </g>
    </svg>
  </div>

  <p v-else-if="!loading && !error" class="muted" style="padding:20px">地图暂无数据。</p>

  <div style="display:flex;gap:14px;margin-top:12px;flex-wrap:wrap" class="muted">
    <span v-for="g in legend" :key="g.key" style="display:inline-flex;align-items:center;gap:6px">
      <span :style="{ width: '9px', height: '9px', borderRadius: '50%', background: g.color, display: 'inline-block' }"></span>
      {{ g.label }}（{{ g.count }} 首）
    </span>
    <span v-if="unlisted.length" style="display:inline-flex;align-items:center;gap:6px">
      <span :style="{ width: '9px', height: '9px', borderRadius: '50%', background: MAP_OTHERS_COLOR, display: 'inline-block' }"></span>
      其余 {{ unlisted.length }} 组（共 {{ unlistedTotal }} 首）
    </span>
  </div>

  <p class="muted" style="margin-top:10px;font-size:12.5px">
    悬停查看方名，点击查看详情。坐标为服务端确定性计算（PCoA 降维），
    同一版本 <span class="mono">version={{ data?.version ?? '—' }}</span>
    反复请求会得到同一张图，可复现、可截图。
    <br />
    分组仅按<b>药味重合度</b>切分，<b>不代表证型、功效或任何医学分类</b>。
    本图共 {{ groups.length }} 个分组，多数只有 1~2 首方；一组一色会让图例比图还长，
    因此按规模从大到小最多给 {{ MAP_MAX_COLORED }} 组上色（本次取到 {{ legend.length }} 组，最小一组 {{ MAP_MIN_GROUP_SIZE }} 首），其余统一灰色。
  </p>

  <NodeDrawer :open="!!current" :title="current?.name ?? ''" @close="current = null">
    <template v-if="current">
      <span class="chip primary">{{ groupText(current.cluster) }}</span>
      <p class="muted" style="margin-top:12px">
        节点 ID：<span class="mono">{{ current.id }}</span>
      </p>
      <p class="muted" style="margin-top:8px;font-size:12.5px">
        与本组其他方剂共用的药味更多，因此投影距离更近。这里只做组成比对，不推断功效。
      </p>
      <div class="hr"></div>
      <div style="display:flex;gap:8px;flex-wrap:wrap">
        <RouterLink class="btn primary sm" :to="`/graph/formula/${encodeURIComponent(current.id)}`">方心子图 →</RouterLink>
        <RouterLink class="btn ghost sm" :to="`/ask?q=${encodeURIComponent(`${current.name}由哪些药组成`)}`">就此提问 →</RouterLink>
      </div>
    </template>
  </NodeDrawer>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import NodeDrawer from '@/components/NodeDrawer.vue'
import { getGraphMap, graphErrMsg, type GraphMapVO } from '@/api/graph'
import {
  CANVAS_H,
  CANVAS_W,
  MAP_MAX_COLORED,
  MAP_MIN_GROUP_SIZE,
  MAP_OTHERS_COLOR,
  layoutMap,
  mapGroups
} from '@/utils/graphLayout'

/**
 * 相似度地图页 —— 数据来自 `/api/biz/graph/map`。
 *
 * 坐标由服务端算（PCoA + 邻域精修，确定性），前端**只做 0~1 → 像素的线性映射**，
 * 绝不重新布局：一旦前端再算一遍，同一 version 的图会每次不一样，讲解和截图都失效。
 *
 * 分组（cluster）只表示"药味重合度高的一群"，配色仅用于区分，不能标成某类方。
 */
const data = ref<GraphMapVO | null>(null)
const loading = ref(false)
const error = ref('')
const limit = ref(150)
const hoverId = ref('')
const current = ref<{ id: string; name: string; cluster: string } | null>(null)

const points = computed(() => (data.value ? layoutMap(data.value) : []))

/** 分组统计（含配色与图例信息），见 `graphLayout.mapGroups` 的取舍说明 */
const groups = computed(() => mapGroups(points.value.map((p) => p.cluster)))
const groupByKey = computed(() => new Map(groups.value.map((g) => [g.key, g])))
const legend = computed(() => groups.value.filter((g) => g.listed))
const unlisted = computed(() => groups.value.filter((g) => !g.listed))
const unlistedTotal = computed(() => unlisted.value.reduce((sum, g) => sum + g.count, 0))

function colorOf(cluster: string): string {
  return groupByKey.value.get(cluster)?.color ?? MAP_OTHERS_COLOR
}

/** 抽屉里显示的组名，如「第 1 组（9 首）」；落在灰色里的显示「其余小组（1 首）」 */
function groupText(cluster: string): string {
  const g = groupByKey.value.get(cluster)
  return g ? `${g.label}（${g.count} 首）` : cluster
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    data.value = await getGraphMap({ limit: limit.value })
  } catch (e) {
    data.value = null
    error.value = graphErrMsg(e)
  } finally {
    loading.value = false
  }
}

function open(p: { id: string; name: string; cluster: string }) {
  current.value = { id: p.id, name: p.name, cluster: p.cluster }
}

onMounted(load)
</script>

<style scoped>
.bubble-node {
  cursor: pointer;
  opacity: 0;
  animation: map-in 0.5s var(--ease) forwards;
}
.bubble-node circle {
  transition: r 0.15s var(--ease), stroke-width 0.15s var(--ease);
}
@keyframes map-in {
  from {
    opacity: 0;
    transform: scale(0.86);
  }
  to {
    opacity: 1;
    transform: none;
  }
}
</style>
