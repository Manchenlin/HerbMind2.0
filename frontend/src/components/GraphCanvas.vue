<template>
  <div class="gcanvas">
    <svg
      :viewBox="`0 0 ${W} ${H}`"
      class="gcanvas-svg"
      role="img"
      aria-label="知识图谱子图"
      @mouseleave="hoverId = ''"
    >
      <!-- 边 -->
      <g>
        <line
          v-for="(e, i) in resolvedEdges"
          :key="`e-${i}`"
          :x1="e.a.x"
          :y1="e.a.y"
          :x2="e.b.x"
          :y2="e.b.y"
          :stroke="isEdgeOn(e) ? '#7FB3A8' : '#C9CFC9'"
          :stroke-width="isEdgeOn(e) ? 2.2 : 1.4"
          class="gedge"
          :style="{ opacity: focusId && !isEdgeOn(e) ? 0.35 : 1 }"
        />
        <template v-if="showRel">
          <text
            v-for="(e, i) in resolvedEdges"
            :key="`r-${i}`"
            :x="(e.a.x + e.b.x) / 2"
            :y="(e.a.y + e.b.y) / 2 - 4"
            text-anchor="middle"
            font-size="10.5"
            fill="#8A938C"
            class="grel"
            :style="{ opacity: isEdgeOn(e) ? 1 : 0 }"
          >{{ REL_CN[e.rel] }}</text>
        </template>
      </g>

      <!-- 节点 -->
      <g
        v-for="(n, i) in nodes"
        :key="n.id"
        class="gnode"
        :style="{ animationDelay: `${Math.min(i * 45, 500)}ms` }"
        @mouseenter="hoverId = n.id"
        @click="emit('select', n.id)"
      >
        <circle
          :cx="n.x"
          :cy="n.y"
          :r="hoverId === n.id ? n.r * 1.12 : n.r"
          :fill="NODE_STYLE[n.label].fill"
          :stroke="NODE_STYLE[n.label].stroke"
          :stroke-width="focusId === n.id ? 3 : 2"
          :opacity="focusId && !linked.has(n.id) ? 0.35 : 1"
        />
        <text
          :x="n.x"
          :y="n.y + 4"
          text-anchor="middle"
          :font-size="n.r >= 28 ? 12 : 10.5"
          :fill="NODE_STYLE[n.label].text"
          :opacity="focusId && !linked.has(n.id) ? 0.35 : 1"
          pointer-events="none"
        >{{ shortName(n.name, n.r) }}</text>
        <title>{{ NODE_LABEL_CN[n.label] }} · {{ n.name }}</title>
      </g>
    </svg>

    <p v-if="!nodes.length" class="muted center" style="padding:26px">该子图没有节点。</p>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { NODE_LABEL_CN, NODE_STYLE, REL_CN, type GEdge, type GNode } from '@/mock/domain3'

/**
 * 轻量 SVG 图谱画布（不引 d3 / 任何图库）。
 * 布局由数据自带 x/y 决定 —— 真接口（svc-graph /neighbors）返回坐标后可直接用；
 * 若后端只返回拓扑，前端再补一层力导布局即可，组件接口不用改。
 */
const props = withDefaults(
  defineProps<{ nodes: GNode[]; edges: GEdge[]; showRel?: boolean; activeId?: string }>(),
  { showRel: true, activeId: '' }
)
const emit = defineEmits<{ (e: 'select', id: string): void }>()

const W = 860
const H = 560
const hoverId = ref('')

const byId = computed(() => new Map(props.nodes.map((n) => [n.id, n])))

type ResolvedEdge = GEdge & { a: GNode; b: GNode }
const resolvedEdges = computed<ResolvedEdge[]>(() => {
  const out: ResolvedEdge[] = []
  for (const e of props.edges) {
    const a = byId.value.get(e.from)
    const b = byId.value.get(e.to)
    if (a && b) out.push({ ...e, a, b })
  }
  return out
})

/** 悬停优先，其次是外部（抽屉）选中的节点 */
const focusId = computed(() => hoverId.value || props.activeId)

const linked = computed(() => {
  const s = new Set<string>()
  if (!focusId.value) return s
  s.add(focusId.value)
  for (const e of props.edges) {
    if (e.from === focusId.value) s.add(e.to)
    if (e.to === focusId.value) s.add(e.from)
  }
  return s
})

function isEdgeOn(e: GEdge) {
  if (!focusId.value) return false
  return e.from === focusId.value || e.to === focusId.value
}

/**
 * 圆内放不下长名字：按半径估可用弦长（2·√(r²−(字号/2)²)）反推出能放几个汉字。
 * r=34 → 4 字；r=22~30 → 3 字；更小的圆 → 2 字。完整名在 <title> 与抽屉里。
 */
function shortName(name: string, r: number) {
  const max = r >= 32 ? 4 : r >= 24 ? 3 : 2
  return name.length > max ? `${name.slice(0, max)}…` : name
}
</script>

<style scoped>
.gcanvas-svg {
  width: 100%;
  display: block;
  background: linear-gradient(135deg, #fbfcfb, #f5f7f6);
}
.gnode {
  cursor: pointer;
  opacity: 0;
  animation: gnode-in 0.45s var(--ease) forwards;
}
.gedge,
.grel {
  transition: opacity 0.2s var(--ease), stroke-width 0.15s var(--ease);
}
.gnode circle,
.gnode text {
  transition: r 0.15s var(--ease), opacity 0.2s var(--ease), stroke-width 0.15s var(--ease);
}
@keyframes gnode-in {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: none;
  }
}
</style>
