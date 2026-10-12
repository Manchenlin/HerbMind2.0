<template>
  <div id="progress"></div>
  <AppHeader />

  <main class="wrap">
    <RouterView />
  </main>

  <footer>
    HerbMind v2 · 视觉基线沿用 <span class="mono">prototype/assets/theme.css</span> ·
    <RouterLink to="/me">我的</RouterLink> ·
    <RouterLink to="/me/favorites">收藏笔记</RouterLink> ·
    <RouterLink to="/admin">治理后台</RouterLink>
  </footer>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import AppHeader from '@/components/AppHeader.vue'

// 原型用 body.loaded 触发入场动画
onMounted(() => document.body.classList.add('loaded'))
</script>
