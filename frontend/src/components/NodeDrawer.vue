<template>
  <div class="overlay" :class="{ open }" @click="emit('close')"></div>
  <aside class="drawer" :class="{ open }" role="dialog" aria-modal="true">
    <div style="padding:20px">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px">
        <h3 class="serif" style="font-size:18px">{{ title }}</h3>
        <button class="btn ghost sm" @click="emit('close')">关闭</button>
      </div>
      <div class="hr"></div>
      <slot />
    </div>
  </aside>
</template>

<script setup lang="ts">
/** 右侧详情抽屉（样式直接用 theme.css 的 .drawer / .overlay）。 */
defineProps<{ open: boolean; title: string }>()
const emit = defineEmits<{ (e: 'close'): void }>()
</script>
