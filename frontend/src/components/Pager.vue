<template>
  <div v-if="total > size" style="display:flex;align-items:center;gap:10px;justify-content:center;margin-top:18px">
    <button class="btn ghost sm" :disabled="page <= 1" @click="go(page - 1)">上一页</button>
    <span class="muted">第 {{ page }} / {{ pages }} 页 · 共 {{ total }} 条</span>
    <button class="btn ghost sm" :disabled="page >= pages" @click="go(page + 1)">下一页</button>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ page: number; total: number; size: number }>()
const emit = defineEmits<{ (e: 'change', page: number): void }>()

const pages = computed(() => Math.max(1, Math.ceil(props.total / Math.max(1, props.size))))

function go(p: number) {
  if (p < 1 || p > pages.value || p === props.page) return
  emit('change', p)
}
</script>
