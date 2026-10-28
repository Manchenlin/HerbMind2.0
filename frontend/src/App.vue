<template>
  <div id="progress"></div>

  <!-- 登录页是整屏两栏布局（照 prototype/login.html），不叠顶栏和页脚 -->
  <AppHeader v-if="!isAuthPage" />

  <main :class="isAuthPage ? '' : 'wrap'">
    <RouterView />
  </main>

  <footer v-if="!isAuthPage">
    HerbMind v2 · 视觉基线沿用 <span class="mono">prototype/assets/theme.css</span> ·
    <RouterLink to="/me">我的</RouterLink> ·
    <RouterLink to="/me/favorites">收藏笔记</RouterLink> ·
    <RouterLink to="/admin">治理后台</RouterLink>
  </footer>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import AppHeader from '@/components/AppHeader.vue'

const route = useRoute()
const isAuthPage = computed(() => route.path === '/login')

// 原型用 body.loaded 触发入场动画
onMounted(() => document.body.classList.add('loaded'))
</script>
