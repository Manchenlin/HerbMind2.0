<template>
  <!--
    能力雷达（与原型 me.html / profile.html 同一套几何算法）。
    只画图形，不做任何数据加工 —— value 必须是 0-100。
  -->
  <svg
    :viewBox="`${PAD} ${PAD} ${SIZE - PAD * 2} ${SIZE - PAD * 2}`"
    style="width: 100%"
    role="img"
    :aria-label="`能力雷达：${items.map((d) => `${d.label} ${d.value}`).join('，')}`"
  >
    <!-- 底环 -->
    <polygon v-for="k in [0.5, 1]" :key="k" class="radar-ring" :points="ringPoints(k)" />

    <!-- 轴线 + 维度名 -->
    <g v-for="(d, i) in items" :key="d.key">
      <line :x1="C" :y1="C" :x2="axisPoint(i).x" :y2="axisPoint(i).y" stroke="#ECECE8" />
      <text
        :x="labelPoint(i).x"
        :y="labelPoint(i).y"
        text-anchor="middle"
        font-size="10.5"
        fill="#6B7280"
      >
        {{ d.label }}
      </text>
    </g>

    <!-- 能力形状 + 顶点 -->
    <polygon class="radar-shape" :points="shapePoints" />
    <circle
      v-for="(p, i) in valuePoints"
      :key="i"
      :cx="p.x"
      :cy="p.y"
      r="2.6"
      fill="var(--primary)"
    />
  </svg>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { RadarItem } from '@/api/me'

const props = withDefaults(defineProps<{ items: RadarItem[]; size?: number }>(), {
  size: 300
})

const SIZE = computed(() => props.size)
const C = computed(() => props.size / 2)
const R = computed(() => props.size / 3)
/** 裁掉图形四周留白，让雷达在卡片里更饱满；裁太多维度名会贴上标题 */
const PAD = 14

function angleOf(i: number) {
  const n = props.items.length || 1
  return -Math.PI / 2 + (i * 2 * Math.PI) / n
}

function ringPoints(k: number) {
  return props.items
    .map((_, i) => {
      const a = angleOf(i)
      return `${C.value + R.value * k * Math.cos(a)},${C.value + R.value * k * Math.sin(a)}`
    })
    .join(' ')
}

const shapePoints = computed(() =>
  props.items
    .map((d, i) => {
      const a = angleOf(i)
      const v = Math.max(0, Math.min(100, d.value ?? 0))
      const r = (R.value * v) / 100
      return `${C.value + r * Math.cos(a)},${C.value + r * Math.sin(a)}`
    })
    .join(' ')
)

const valuePoints = computed(() =>
  props.items.map((d, i) => {
    const a = angleOf(i)
    const v = Math.max(0, Math.min(100, d.value ?? 0))
    const r = (R.value * v) / 100
    return { x: C.value + r * Math.cos(a), y: C.value + r * Math.sin(a) }
  })
)

function axisPoint(i: number) {
  const a = angleOf(i)
  return { x: C.value + R.value * Math.cos(a), y: C.value + R.value * Math.sin(a) }
}

function labelPoint(i: number) {
  const a = angleOf(i)
  const r = R.value + 22
  return { x: C.value + r * Math.cos(a), y: C.value + r * Math.sin(a) }
}
</script>
