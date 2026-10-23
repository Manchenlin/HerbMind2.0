<template>
  <div class="crumb">
    <RouterLink to="/">首页</RouterLink> / <RouterLink to="/admin">治理后台</RouterLink> / OCR 疑点
  </div>

  <h1 class="serif" style="margin-bottom:6px">OCR 疑点</h1>
  <p class="muted" style="margin-bottom:16px">
    异体字 / 剂量未结构化 / 方名缩写 / 案例粘连四类。共 {{ issues.length }} 条，待处理 {{ openIssueCount }} 条。
    <b>示意数据</b>：<span class="mono">svc-governance</span> 未建，标记处理不会写库。
  </p>

  <AdminTabs />

  <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px;align-items:center">
    <span class="chip clickable" :class="{ sel: filter === '全部' }" @click="filter = '全部'">全部 {{ issues.length }}</span>
    <span
      v-for="k in kinds"
      :key="k"
      class="chip clickable"
      :class="{ sel: filter === k }"
      @click="filter = k"
    >{{ k }}</span>
    <span class="spacer" style="flex:1"></span>
    <button class="btn ghost sm" @click="markAllShown">把当前筛选全部标记已处理</button>
  </div>

  <section class="card">
    <div class="stagger" style="display:grid;gap:10px">
      <div v-for="i in shown" :key="i.id" class="rowitem" style="align-items:center">
        <span class="thumb" :style="thumbStyle(i)">{{ i.kind.slice(0, 1) }}</span>
        <div style="flex:1;min-width:0">
          <b>{{ i.title }}</b>
          <div class="muted">{{ i.detail }}</div>
        </div>
        <span class="chip" style="margin-right:10px">{{ i.kind }}</span>
        <span class="badge" :class="i.resolved ? 'ok' : i.severity === 'err' ? 'err' : 'warn'">
          {{ i.resolved ? '已处理' : '待处理' }}
        </span>
        <button v-if="!i.resolved" class="btn ghost sm" style="margin-left:8px" @click="doResolve(i.id)">
          标记已处理
        </button>
      </div>
      <p v-if="!shown.length" class="muted">该筛选下没有疑点。</p>
    </div>
  </section>

  <p class="muted" style="margin-top:12px">
    真实实现要落到 <span class="mono">content_review / issue</span> 两张表（见 06 数据库设计），
    并由 <span class="mono">svc-governance</span> 提供 <span class="mono">/internal/governance/**</span>。
  </p>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import AdminTabs from '@/components/AdminTabs.vue'
import { useGovernance } from '@/composables/useGovernance'
import type { IssueItem } from '@/mock/domain3'
import { toast } from '@/utils/toast'

const { issues, openIssueCount, resolveIssue } = useGovernance()

const kinds: Array<IssueItem['kind']> = ['异体字', '剂量', '命名', '粘连']
const filter = ref<'全部' | IssueItem['kind']>('全部')

const shown = computed(() =>
  filter.value === '全部' ? issues.value : issues.value.filter((i) => i.kind === filter.value)
)

function thumbStyle(i: IssueItem) {
  if (i.resolved) return 'background:var(--success-soft);color:#1E7A50'
  if (i.severity === 'err') return 'background:var(--error-soft);color:#9A2F26'
  return 'background:var(--warning-soft);color:#9A6E14'
}

function doResolve(id: string) {
  resolveIssue(id)
  toast('已标记处理（本地状态，未写库）')
}

function markAllShown() {
  const targets = shown.value.filter((i) => !i.resolved)
  targets.forEach((i) => resolveIssue(i.id))
  toast(targets.length ? `已标记 ${targets.length} 条` : '没有待处理项')
}
</script>
