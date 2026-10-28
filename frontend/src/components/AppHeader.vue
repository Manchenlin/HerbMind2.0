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

      <RouterLink class="btn primary sm" v-if="!user" to="/login">登录 / 注册</RouterLink>

      <!-- 已登录：头像 + 昵称，点击进入「我的」 -->
      <RouterLink v-else class="me-entry" to="/me" :title="`${displayName} · 进入我的`">
        <span class="avatar">{{ initial }}</span>
        <span class="me-name">{{ displayName }}</span>
      </RouterLink>
    </div>
  </header>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { toast } from '@/utils/toast'
import { me, type UserDto } from '@/api/user'

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
  { id: 'bk_1', title: '伤寒论', current: true, planned: false },
  { id: 'bk_2', title: '温病学', current: false, planned: false },
  { id: 'bk_3', title: '金匮要略', current: false, planned: false }
]
const bookId = ref('bk_1')

const route = useRoute()
function isActive(to: string) {
  return to === '/' ? route.path === '/' : route.path.startsWith(to)
}

function onSwitch() {
  const b = books.find((x) => x.id === bookId.value)
  if (!b) return
  if (b.planned) {
    toast(`「${b.title}」规划中，敬请期待`)
    bookId.value = 'bk_1'
    return
  }
  toast(`已切换语料：${b.title}`)
}

/* ---------- 登录态：右上角显示「头像 + 昵称」，点进 /me ---------- */
const user = ref<UserDto | null>(null)
const displayName = computed(() => user.value?.nickname || user.value?.username || '')
const initial = computed(() => displayName.value.slice(0, 1) || '我')

async function loadUser() {
  if (!localStorage.getItem('token')) {
    user.value = null
    return
  }
  try {
    user.value = await me()
  } catch {
    // token 失效：拦截器会跳登录页，这里静默降级成「未登录」样式
    user.value = null
  }
}

onMounted(loadUser)
// 登录 / 登出都会换路由，顺带刷新一下头像状态
watch(() => route.path, loadUser)
</script>

<style scoped>
.me-entry {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 3px 10px 3px 3px;
  border-radius: 999px;
  border: 1px solid transparent;
  transition: background 0.16s, border-color 0.16s;
}

.me-entry:hover {
  background: var(--surface-2);
  border-color: var(--border);
}

.me-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text);
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
