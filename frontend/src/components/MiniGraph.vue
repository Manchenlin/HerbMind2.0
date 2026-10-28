<template>
  <svg :viewBox="`0 0 ${W} ${H}`" style="width:100%;height:auto;display:block">
    <g v-for="(e, i) in edgeLines" :key="'e' + i">
      <line :x1="e.x1" :y1="e.y1" :x2="e.x2" :y2="e.y2" stroke="#C9CFC9" stroke-width="1.2" />
    </g>
    <g v-for="n in positioned" :key="n.id" style="cursor:pointer" @click="$emit('pick', n)">
      <circle
        :cx="n.x"
        :cy="n.y"
        :r="n.r"
        :fill="fillOf(n.type)"
        :stroke="strokeOf(n.type)"
        stroke-width="2"
      />
      <text
        :x="n.x"
        :y="n.y + 4"
        text-anchor="middle"
        :font-size="n.r > 20 ? 11 : 10"
        :fill="textOf(n.type)"
      >{{ n.name }}</text>
    </g>
    <text v-if="!positioned.length" :x="W / 2" :y="H / 2" text-anchor="middle" font-size="12" fill="#9AA0A6">
      暂无图谱预览
    </text>
  </svg>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { GraphPreview } from '@/api/home'

const props = defineProps<{
  graph?: GraphPreview | null
  w?: number
  h?: number
}>()

defineEmits<{ (e: 'pick', node: { id: string; type: string; name: string }): void }>()

const W = computed(() => props.w ?? 480)
const H = computed(() => props.h ?? 300)

const sized = computed(() => {
  const nodes = props.graph?.nodes ?? []
  if (!nodes.length) return []
  const center = nodes.find((n) => n.level === 0) ?? nodes[0]
  if (!center) return []
  const ring1 = nodes.filter((n) => n !== center && n.level <= 1)
  const ring2 = nodes.filter((n) => n !== center && n.level > 1)
  const cx = W.value / 2
  const cy = H.value / 2

  const place = (list: typeof nodes, radius: number, start: number) =>
    list.map((n, i) => {
      const angle = start + (i / Math.max(1, list.length)) * Math.PI * 2
      return {
        ...n,
        x: Math.round(cx + Math.cos(angle) * radius),
        y: Math.round(cy + Math.sin(angle) * radius),
        r: n === center ? 30 : n.type === 'Herb' ? 18 : 22
      }
    })

  return [
    { ...center, x: cx, y: cy, r: 30 },
    ...place(ring1, 110, -Math.PI / 2),
    ...place(ring2, 165, 0)
  ]
})

const positioned = computed(() => sized.value)

const posById = computed(() => {
  const m: Record<string, { x: number; y: number }> = {}
  for (const n of positioned.value) m[n.id] = { x: n.x, y: n.y }
  return m
})

const edgeLines = computed(() =>
  (props.graph?.edges ?? [])
    .map((e) => {
      const a = posById.value[e.source]
      const b = posById.value[e.target]
      return a && b ? { x1: a.x, y1: a.y, x2: b.x, y2: b.y } : null
    })
    .filter((x): x is { x1: number; y1: number; x2: number; y2: number } => x !== null)
)

function fillOf(type: string) {
  if (type === 'Formula') return '#E6F2EF'
  if (type === 'Herb') return '#EAF2FC'
  if (type === 'Syndrome') return '#FBEDE7'
  return '#E9F3F2'
}

function strokeOf(type: string) {
  if (type === 'Formula') return '#2E7D6F'
  if (type === 'Herb') return '#3B7DD8'
  if (type === 'Syndrome') return '#D9724E'
  return '#4F8A8B'
}

function textOf(type: string) {
  if (type === 'Formula') return '#1F5C52'
  if (type === 'Herb') return '#2A5DA0'
  if (type === 'Syndrome') return '#B4552F'
  return '#376566'
}
</script>
