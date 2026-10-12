<template>
  <h2>典籍浏览</h2>
  <p style="color:#6b6b68">当前语料：{{ bookId }}</p>

  <el-alert v-if="error" :title="error" type="error" :closable="false" style="margin-bottom:12px" />

  <el-tree
    v-loading="loading"
    :data="tree"
    :props="{ label: 'title', children: 'children' }"
    node-key="id"
    default-expand-all
  />
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { getLibraryTree, type BookTreeNode } from '@/api/catalog'

const bookId = ref('fz')
const tree = ref<BookTreeNode[]>([])
const loading = ref(false)
const error = ref('')

onMounted(async () => {
  loading.value = true
  try {
    tree.value = await getLibraryTree(bookId.value)
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    loading.value = false
  }
})
</script>
