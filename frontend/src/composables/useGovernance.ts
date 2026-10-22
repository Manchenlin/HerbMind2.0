import { computed, ref } from 'vue'
import { DEMO_AUDIT, DEMO_ISSUES, DEMO_REVIEWS, type AuditItem, type IssueItem, type ReviewItem } from '@/mock/domain3'
import { getHealth } from '@/api/agent'

/**
 * 治理后台状态。
 *
 * `svc-governance`（:8087）还没建，所以工单/疑点是**示意数据**，通过/驳回只改本地状态，
 * 不会真的落库——页面上已标注，别让人误以为操作生效了。
 * 真实数字只有两个：PG 里的 content_unit 条数与向量覆盖（读 /api/agent/health）。
 */

const reviews = ref<ReviewItem[]>(DEMO_REVIEWS.map((r) => ({ ...r })))
const issues = ref<IssueItem[]>(DEMO_ISSUES.map((i) => ({ ...i })))
const audit = ref<AuditItem[]>([...DEMO_AUDIT])

/** health 里解析出的真实规模；取不到就 null（页面显示 "—"，不编数） */
const realStats = ref<{ contentUnit: number | null; vectors: number | null; ok: boolean }>({
  contentUnit: null,
  vectors: null,
  ok: false
})

let probed = false

async function probe() {
  if (probed) return
  probed = true
  try {
    const h = await getHealth()
    const detail = h.deps?.postgres?.detail ?? ''
    const cu = /content_unit=(\d+)/.exec(detail)
    const vec = /vectors=(\d+)/.exec(detail)
    realStats.value = {
      contentUnit: cu ? Number(cu[1]) : null,
      vectors: vec ? Number(vec[1]) : null,
      ok: Boolean(h.deps?.postgres?.ok)
    }
  } catch {
    realStats.value = { contentUnit: null, vectors: null, ok: false }
  }
}

function nowLabel() {
  const d = new Date()
  const p = (n: number) => String(n).padStart(2, '0')
  return `今天 ${p(d.getHours())}:${p(d.getMinutes())}`
}

function appendAudit(action: AuditItem['action'], target: string) {
  audit.value = [{ time: nowLabel(), operator: 'me', action, target }, ...audit.value]
}

function approve(id: string) {
  const r = reviews.value.find((x) => x.id === id)
  if (!r) return
  r.status = 'passed'
  appendAudit('通过', r.title)
}

function reject(id: string) {
  const r = reviews.value.find((x) => x.id === id)
  if (!r) return
  r.status = 'rejected'
  appendAudit('驳回', r.title)
}

function resolveIssue(id: string) {
  const i = issues.value.find((x) => x.id === id)
  if (!i) return
  i.resolved = true
  i.severity = 'ok'
  i.detail = '已处理（本地标记，未写库）'
}

export function useGovernance() {
  const pendingCount = computed(() => reviews.value.filter((r) => r.status === 'pending').length)
  const openIssueCount = computed(() => issues.value.filter((i) => !i.resolved).length)

  return {
    reviews,
    issues,
    audit,
    realStats,
    pendingCount,
    openIssueCount,
    probe,
    approve,
    reject,
    resolveIssue
  }
}
