<template>
  <header class="topbar">
    <div class="inner">
      <RouterLink class="brand" to="/"><span class="logo">H</span>HerbMind 本草心智</RouterLink>

      <nav class="nav">
        <RouterLink
          v-for="n in NAV"
          :key="n.to"
          :to="n.to"
          :class="{ active: isActive(n.to) }"
        >{{ n.label }}</RouterLink>
      </nav>

      <span class="spacer"></span>

      <select class="booksel" title="切换语料（插拔式）" v-model="bookId" @change="onSwitch">
        <option v-for="b in books" :key="b.id" :value="b.id">
          {{ b.current ? '★ ' : '' }}{{ b.title }}{{ b.planned ? '（规划中）' : '' }}
        </option>
      </select>

      <RouterLink class="btn primary sm" to="/login">登录 / 注册</RouterLink>
    </div>
  </header>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRoute } from 'vue-router'
import { toast } from '@/utils/toast'

// 一级导航（与原型 assets/app.js 的 NAV 一致）
const NAV = [
  { to: '/', label: '首页' },
  { to: '/shelf', label: '书架' },
  { to: '/library', label: '典籍' },
  { to: '/search', label: '检索' },
  { to: '/train', label: '练习' },
  { to: '/graph', label: '图谱' },
  { to: '/ask', label: '智能问答' },
  { to: '/me', label: '我的' }
]

const books = [
  { id: 'fz', title: '中医经典方证案例研究', current: true, planned: false },
  { id: 'sh', title: '伤寒论原文', current: false, planned: false },
  { id: 'jg', title: '金匮要略', current: false, planned: true }
]
const bookId = ref('fz')

const route = useRoute()
function isActive(to: string) {
  return to === '/' ? route.path === '/' : route.path.startsWith(to)
}

function onSwitch() {
  const b = books.find((x) => x.id === bookId.value)
  if (!b) return
  if (b.planned) {
    toast(`「${b.title}」规划中，敬请期待`)
    bookId.value = 'fz'
    return
  }
  toast(`已切换语料：${b.title}`)
}
</script>
