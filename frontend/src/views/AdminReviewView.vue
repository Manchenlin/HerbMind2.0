<template>
  <div class="crumb"><RouterLink to="/">首页</RouterLink> / <RouterLink to="/admin">治理后台</RouterLink> / 复核工单</div>

  <h1 class="serif" style="margin-bottom:6px">复核工单</h1>
  <p class="muted" style="margin-bottom:16px">
    待复核 {{ pendingCount }} 条 · 通过 / 驳回只改本地状态，
    <span class="mono">/internal/governance/**</span> 落地后才会真正写库。
  </p>

  <AdminTabs />

  <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px;align-items:center">
    <span class="chip clickable" :class="{ sel: filter === 'all' }" @click="filter = 'all'">全部 {{ reviews.length }}</span>
    <span class="chip clickable" :class="{ sel: filter === 'pending' }" @click="filter = 'pending'">待复核 {{ pendingCount }}</span>
    <span class="chip clickable" :class="{ sel: filter === 'passed' }" @click="filter = 'passed'">已通过 {{ countBy('passed') }}</span>
    <span class="chip clickable" :class="{ sel: filter === 'rejected' }" @click="filter = 'rejected'">已驳回 {{ countBy('rejected') }}</span>
  </div>

  <section class="card">
    <table class="tb">
      <thead>
        <tr><th>条目</th><th>类型</th><th>章节</th><th>提交人</th><th>提交时间</th><th>状态</th><th>操作</th></tr>
      </thead>
      <tbody>
        <tr v-for="r in shown" :key="r.id">
          <td>
            <a style="cursor:pointer;font-weight:600" @click="open(r)">{{ r.title }}</a>
          </td>
          <td><span class="badge" :class="typeBadge(r.type)">{{ r.type }}</span></td>
          <td class="muted">{{ r.chapter }}</td>
          <td class="muted">{{ r.submitter }}</td>
          <td class="muted">{{ r.submittedAt }}</td>
          <td><span class="badge" :class="statusBadge(r.status)">{{ statusText(r.status) }}</span></td>
          <td>
            <template v-if="r.status === 'pending'">
              <button class="btn ghost sm" @click="doApprove(r.id)">通过</button>
              <button class="btn ghost sm" style="margin-left:6px" @click="doReject(r.id)">驳回</button>
            </template>
            <span v-else class="muted">已处理</span>
          </td>
        </tr>
        <tr v-if="!shown.length">
          <td colspan="7" class="muted">该筛选下没有工单。</td>
        </tr>
      </tbody>
    </table>
  </section>

  <NodeDrawer :open="!!current" :title="current?.title ?? ''" @close="current = null">
    <template v-if="current">
      <span class="badge" :class="typeBadge(current.type)">{{ current.type }}</span>
      <span class="badge info" style="margin-left:6px">{{ current.chapter }}</span>
      <p class="muted" style="margin-top:12px">
        提交人：{{ current.submitter }}<br />
        提交时间：{{ current.submittedAt }}<br />
        当前状态：<span class="badge" :class="statusBadge(current.status)">{{ statusText(current.status) }}</span>
      </p>
      <div class="hr"></div>
      <p class="muted" style="font-size:13px">
        「通过 / 驳回」的真实语义（见 09 契约）：更新 <span class="mono">content_review</span> 状态 +
        写 <span class="mono">audit_log</span>。接口未实现，这里只做交互演示。
      </p>
      <div style="display:flex;gap:8px;margin-top:12px" v-if="current.status === 'pending'">
        <button class="btn primary sm" @click="doApprove(current.id)">通过</button>
        <button class="btn ghost sm" @click="doReject(current.id)">驳回</button>
      </div>
    </template>
  </NodeDrawer>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import AdminTabs from '@/components/AdminTabs.vue'
import NodeDrawer from '@/components/NodeDrawer.vue'
import { useGovernance } from '@/composables/useGovernance'
import type { ReviewItem } from '@/mock/domain3'
import { toast } from '@/utils/toast'

const { reviews, pendingCount, approve, reject } = useGovernance()

type Filter = 'all' | 'pending' | 'passed' | 'rejected'
const filter = ref<Filter>('pending')
const current = ref<ReviewItem | null>(null)

const shown = computed(() =>
  filter.value === 'all' ? reviews.value : reviews.value.filter((r) => r.status === filter.value)
)

function countBy(s: ReviewItem['status']) {
  return reviews.value.filter((r) => r.status === s).length
}

function typeBadge(t: ReviewItem['type']) {
  return t === '案例' ? 'warn' : t === '方剂' ? 'info' : 'ok'
}

function statusBadge(s: ReviewItem['status']) {
  return s === 'pending' ? 'warn' : s === 'passed' ? 'ok' : 'err'
}

function statusText(s: ReviewItem['status']) {
  return s === 'pending' ? '待复核' : s === 'passed' ? '已通过' : '已驳回'
}

function open(r: ReviewItem) {
  current.value = r
}

function doApprove(id: string) {
  approve(id)
  toast('已通过（本地状态，未写库）')
}

function doReject(id: string) {
  reject(id)
  toast('已驳回（本地状态，未写库）')
}
</script>
