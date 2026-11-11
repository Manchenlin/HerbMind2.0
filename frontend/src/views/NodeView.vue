<template>
  <div class="crumb">
    <RouterLink to="/">首页</RouterLink> /
    <RouterLink to="/library">典籍</RouterLink>
    <template v-if="d?.bookTitle"> / {{ d.bookTitle }}</template>
    <template v-if="d">
      <template v-for="b in d.breadcrumb" :key="b.id">
        / <RouterLink :to="`/node/${b.id}`">{{ b.name }}</RouterLink>
      </template>
      / {{ d.node.title }}
    </template>
  </div>

  <!-- 详情主体在 components/NodeDetail.vue：典籍页右侧内嵌的是同一个组件 -->
  <NodeDetail :id="id" @loaded="onLoaded">
    <template #actions>
      <RouterLink class="chip clickable" to="/library">← 返回典籍</RouterLink>
    </template>
  </NodeDetail>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import NodeDetail from '@/components/NodeDetail.vue'
import type { NodeDetail as NodeDetailData } from '@/api/catalog'

const route = useRoute()
const id = computed(() => String(route.params.id))

/** 只为面包屑留着：主体渲染由子组件负责，它加载完把数据抛上来 */
const d = ref<NodeDetailData | null>(null)

function onLoaded(detail: NodeDetailData) {
  d.value = detail
}
</script>
