<template>
  <div class="crumb">
    <RouterLink to="/">首页</RouterLink> / <RouterLink to="/me">我的</RouterLink> / 收藏夹
  </div>
  <h1 class="serif" style="margin-bottom: 6px">收藏夹</h1>
  <p class="muted" style="margin-bottom: 22px">
    方剂、医案、条文都能收藏；打开条目即可跳到对应内容页。
  </p>

  <div v-if="loading" class="card"><p class="muted">正在加载收藏…</p></div>
  <div v-else-if="error" class="card">
    <p class="muted" style="color: #a32d2d; margin-bottom: 12px">{{ error }}</p>
    <button class="btn ghost sm" @click="load">重试</button>
  </div>

  <div v-else-if="!data.items.length" class="card center" style="padding: 48px 20px">
    <div style="font-size: 44px">🔖</div>
    <p class="muted" style="margin: 12px 0 16px">
      还没有收藏。在方剂 / 医案 / 条文页点「收藏」就会出现在这里。
    </p>
    <RouterLink class="btn primary sm" to="/library">去逛典籍</RouterLink>
  </div>

  <template v-else>
    <div class="muted" style="margin-bottom: 12px">共 {{ data.total }} 条</div>
    <div class="grid cols-2">
      <div v-for="f in data.items" :key="f.id" class="rowitem">
        <span class="thumb">{{ f.title.slice(0, 1) }}</span>
        <div style="flex: 1; min-width: 0">
          <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap">
            <RouterLink :to="f.link" style="font-weight: 700">{{ f.title }}</RouterLink>
            <span class="chip" style="font-size: 11px">{{ f.targetLabel }}</span>
            <span class="muted" style="font-size: 12px">收藏于 {{ f.createdLabel }}</span>
          </div>
          <div class="muted" style="margin-top: 4px">{{ f.subtitle || '—' }}</div>
        </div>
        <button class="btn ghost sm" @click="remove(f.id)">取消收藏</button>
      </div>
    </div>
    <p v-if="actionError" class="muted" style="color: #a32d2d; margin-top: 12px">
      {{ actionError }}
    </p>
  </template>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { getFavorites, removeFavorite, type FavoriteList } from '@/api/me'

const data = ref<FavoriteList>({ items: [], total: 0 })
const loading = ref(true)
const error = ref('')
const actionError = ref('')

async function load() {
  loading.value = true
  error.value = ''
  try {
    data.value = await getFavorites()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

async function remove(id: number) {
  actionError.value = ''
  try {
    data.value = await removeFavorite(id)
  } catch (e) {
    actionError.value = e instanceof Error ? e.message : '取消失败，请稍后重试'
  }
}

onMounted(load)
</script>
