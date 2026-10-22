<template>
  <div class="crumb"><RouterLink to="/">首页</RouterLink> / 治理后台</div>

  <h1 class="serif" style="margin-bottom:6px">数据治理后台</h1>
  <p class="muted" style="margin-bottom:16px">
    内容校验流转 · 复核工单 · OCR 疑点 · 操作留痕。
    <b>工单与疑点为示意数据</b>（<span class="mono">svc-governance</span> :8087 未建）；
    规模数字读自 <span class="mono">/api/agent/health</span>，是真实的。
  </p>

  <AdminTabs />

  <section class="grid cols-4 stagger" style="margin-bottom:24px">
    <div class="stat">
      <div class="n count">{{ pendingCount }}</div>
      <div class="l">待复核（本地示意）</div>
    </div>
    <div class="stat">
      <div class="n count">{{ openIssueCount }}</div>
      <div class="l">OCR 疑点（本地示意）</div>
    </div>
    <div class="stat">
      <div class="n count">{{ realStats.contentUnit ?? '—' }}</div>
      <div class="l">内容单元（PG 实测）</div>
    </div>
    <div class="stat">
      <div class="n count">{{ realStats.vectors ?? '—' }}</div>
      <div class="l">已建向量（PG 实测）</div>
    </div>
  </section>

  <div class="grid cols-2" style="align-items:start">
    <section class="card">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px">
        <h3>待复核内容</h3>
        <RouterLink class="chip clickable" to="/admin/review">全部工单 →</RouterLink>
      </div>
      <table class="tb">
        <thead>
          <tr><th>条目</th><th>类型</th><th>章节</th><th>操作</th></tr>
        </thead>
        <tbody>
          <tr v-for="r in pending.slice(0, 3)" :key="r.id">
            <td>{{ r.title }}</td>
            <td><span class="badge" :class="typeBadge(r.type)">{{ r.type }}</span></td>
            <td class="muted">{{ r.chapter }}</td>
            <td>
              <button class="btn ghost sm" @click="doApprove(r.id)">通过</button>
              <button class="btn ghost sm" style="margin-left:6px" @click="doReject(r.id)">驳回</button>
            </td>
          </tr>
          <tr v-if="!pending.length">
            <td colspan="4" class="muted">没有待复核条目了。</td>
          </tr>
        </tbody>
      </table>
    </section>

    <section class="card">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px">
        <h3>OCR 疑点清单</h3>
        <RouterLink class="chip clickable" to="/admin/issues">全部疑点 →</RouterLink>
      </div>
      <div class="stagger" style="display:grid;gap:10px">
        <div v-for="i in issues.slice(0, 4)" :key="i.id" class="rowitem">
          <span class="thumb" :style="thumbStyle(i.severity)">{{ i.kind.slice(0, 1) }}</span>
          <div style="flex:1">
            <b>{{ i.title }}</b>
            <div class="muted">{{ i.detail }}</div>
          </div>
          <span class="badge" :class="i.resolved ? 'ok' : i.severity === 'err' ? 'err' : 'warn'">
            {{ i.resolved ? '已处理' : '待处理' }}
          </span>
        </div>
      </div>
    </section>
  </div>

  <section class="card" style="margin-top:20px">
    <h3 style="margin-bottom:14px">操作审计（本地记录，未写库）</h3>
    <table class="tb">
      <thead>
        <tr><th>时间</th><th>操作者</th><th>动作</th><th>对象</th></tr>
      </thead>
      <tbody>
        <tr v-for="(a, i) in audit" :key="i">
          <td class="muted">{{ a.time }}</td>
          <td>{{ a.operator }}</td>
          <td>
            <span class="badge" :class="a.action === '通过' ? 'ok' : a.action === '驳回' ? 'err' : 'info'">
              {{ a.action }}
            </span>
          </td>
          <td>{{ a.target }}</td>
        </tr>
      </tbody>
    </table>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import AdminTabs from '@/components/AdminTabs.vue'
import { useGovernance } from '@/composables/useGovernance'
import type { IssueItem, ReviewItem } from '@/mock/domain3'
import { toast } from '@/utils/toast'

const { reviews, issues, audit, realStats, pendingCount, openIssueCount, probe, approve, reject } = useGovernance()

const pending = computed(() => reviews.value.filter((r) => r.status === 'pending'))

function typeBadge(t: ReviewItem['type']) {
  return t === '案例' ? 'warn' : t === '方剂' ? 'info' : 'ok'
}

function thumbStyle(sev: IssueItem['severity']) {
  if (sev === 'err') return 'background:var(--error-soft);color:#9A2F26'
  if (sev === 'warn') return 'background:var(--warning-soft);color:#9A6E14'
  return 'background:var(--success-soft);color:#1E7A50'
}

function doApprove(id: string) {
  approve(id)
  toast('已通过（本地状态，未写库）')
}

function doReject(id: string) {
  reject(id)
  toast('已驳回（本地状态，未写库）')
}

onMounted(probe)
</script>
