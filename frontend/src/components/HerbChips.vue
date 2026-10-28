<template>
  <div style="display:flex;gap:8px;flex-wrap:wrap">
    <span v-for="h in herbs" :key="h.name + (h.seq ?? '')" class="chip">
      {{ h.name }}<template v-if="showDose && h.dose !== undefined && h.dose !== null">
        {{ ' ' + doseText(h) }}</template>
      <span v-if="h.role" class="role" :class="roleClass(h.role)">{{ h.role }}</span>
    </span>
    <span v-if="!herbs.length" class="muted">（未收录药味）</span>
  </div>
</template>

<script setup lang="ts">
import type { Herb } from '@/api/catalog'
import { doseText, roleClass } from '@/utils/format'

withDefaults(
  defineProps<{
    herbs: Herb[]
    showDose?: boolean
  }>(),
  { showDose: true }
)
</script>
