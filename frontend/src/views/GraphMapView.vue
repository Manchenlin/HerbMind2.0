<template>
  <div class="crumb">
    <RouterLink to="/">首页</RouterLink> / <RouterLink to="/graph">图谱</RouterLink> / 相似度地图
  </div>

  <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:14px;flex-wrap:wrap;margin-bottom:12px">
    <div>
      <h1 class="serif" style="font-size:24px">方证相似度地图</h1>
      <p class="muted" style="margin-top:4px">
        方剂按药味 / 证候向量降维投影到 2D，邻近者相似，聚成「方剂星系」。
        当前 {{ totalPoints }} 首方 · {{ DEMO_MAP.length }} 个星系。
      </p>
    </div>
    <RouterLink class="chip clickable" to="/graph">← 返回图谱</RouterLink>
  </div>

  <div class="card" style="padding:0;overflow:hidden">
    <svg viewBox="0 0 860 540" style="width:100%;display:block;background:radial-gradient(circle at 40% 40%,#FBFCFB,#EFF3F1)">
      <defs>
        <radialGradient v-for="(c, i) in centers" :id="`halo-${i}`" :key="`g-${i}`">
          <stop offset="0%" :stop-color="DEMO_MAP[i].color" stop-opacity="0.16" />
          <stop offset="100%" :stop-color="DEMO_MAP[i].color" stop-opacity="0" />
        </radialGradient>
      </defs>

      <!-- 星系光晕 -->
      <circle
        v-for="(c, i) in centers"
        :key="`halo-c-${i}`"
        :cx="c.x"
        :cy="c.y"
        r="132"
        :fill="`url(#halo-${i})`"
      />

      <!-- 方剂气泡 -->
      <g
        v-for="(p, i) in points"
        :key="p.key"
        class="bubble-node"
        :style="{ animationDelay: `${Math.min(i * 40, 420)}ms` }"
        @mouseenter="hoverKey = p.key"
        @mouseleave="hoverKey = ''"
        @click="open(p.name, p.clusterName, p.note)"
      >
        <circle
          :cx="p.x"
          :cy="p.y"
          :r="hoverKey === p.key ? p.r * 1.1 : p.r"
          :fill="`${p.color}22`"
          :stroke="p.color"
          stroke-width="1.6"
        />
        <text
          :x="p.x"
          :y="p.y + 4"
          text-anchor="middle"
          font-size="11"
          fill="#1F2328"
          pointer-events="none"
        >{{ p.name }}</text>
      </g>
    </svg>
  </div>

  <div style="display:flex;gap:14px;margin-top:12px;flex-wrap:wrap" class="muted">
    <span v-for="c in DEMO_MAP" :key="c.name" style="display:inline-flex;align-items:center;gap:6px">
      <span :style="{ width: '9px', height: '9px', borderRadius: '50%', background: c.color, display: 'inline-block' }"></span>
      {{ c.name }}（{{ c.note }}）
    </span>
  </div>

  <p class="muted" style="margin-top:10px">
    坐标为<b>示意数据</b> · 待 <span class="mono">svc-graph /internal/graph/map</span>（真实 UMAP/PCA 投影）落地后替换。
  </p>

  <NodeDrawer :open="!!current" :title="current?.name ?? ''" @close="current = null">
    <template v-if="current">
      <span class="chip primary">{{ current.cluster }}</span>
      <span class="chip" style="margin-left:6px">{{ current.note }}</span>
      <p class="muted" style="margin-top:12px">
        与同簇方剂药味 / 证候向量距离较近；具体相似度数值待后端接口提供。
      </p>
      <div class="hr"></div>
      <div style="display:flex;gap:8px;flex-wrap:wrap">
        <RouterLink class="btn primary sm" :to="`/graph/formula/${current.id}`">方心子图 →</RouterLink>
        <RouterLink class="btn ghost sm" :to="`/ask?q=${encodeURIComponent(`${current.name}与同类的区别`)}`">就此提问 →</RouterLink>
      </div>
    </template>
  </NodeDrawer>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import NodeDrawer from '@/components/NodeDrawer.vue'
import { DEMO_MAP, resolveNodeId } from '@/mock/domain3'

const hoverKey = ref('')
const current = ref<{ name: string; id: string; cluster: string; note: string } | null>(null)

/** 展平成一维，便于 v-for 和 key */
const points = computed(() =>
  DEMO_MAP.flatMap((c) =>
    c.points.map((p) => ({
      key: `${c.name}-${p.name}`,
      name: p.name,
      x: p.x,
      y: p.y,
      r: p.r,
      color: c.color,
      clusterName: c.name,
      note: c.note
    }))
  )
)

const totalPoints = computed(() => points.value.length)

/** 星系质心：用其成员坐标平均，光晕才不会飘 */
const centers = computed(() =>
  DEMO_MAP.map((c) => ({
    x: c.points.reduce((s, p) => s + p.x, 0) / c.points.length,
    y: c.points.reduce((s, p) => s + p.y, 0) / c.points.length
  }))
)

/** 地图数据只有方名，进方心子图前先解析成示意图里的节点 ID */
function open(name: string, cluster: string, note: string) {
  current.value = { name, id: resolveNodeId(name), cluster, note }
}
</script>

<style scoped>
.bubble-node {
  cursor: pointer;
  opacity: 0;
  animation: map-in 0.5s var(--ease) forwards;
}
.bubble-node circle {
  transition: r 0.15s var(--ease), opacity 0.15s var(--ease);
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
