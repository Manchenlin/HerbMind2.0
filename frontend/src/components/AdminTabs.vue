<template>
  <span class="pill-tabs admin-tabs">
    <button :class="{ active: route.path === '/admin' }" @click="go('/admin')">总览</button>
    <button :class="{ active: route.path === '/admin/review' }" @click="go('/admin/review')">
      复核工单 <span class="muted">({{ pendingCount }})</span>
    </button>
    <button :class="{ active: route.path === '/admin/issues' }" @click="go('/admin/issues')">
      OCR 疑点 <span class="muted">({{ openIssueCount }})</span>
    </button>
  </span>
</template>

<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'
import { useGovernance } from '@/composables/useGovernance'

const route = useRoute()
const router = useRouter()
const { pendingCount, openIssueCount } = useGovernance()

function go(p: string) {
  router.push(p)
}
</script>

<style scoped>
.admin-tabs {
  margin-bottom: 16px;
}
.admin-tabs .muted {
  font-weight: 400;
  font-size: 12px;
}
</style>
