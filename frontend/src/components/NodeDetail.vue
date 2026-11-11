<template>
  <div v-if="loading" class="card">
    <p class="muted">加载中…</p>
  </div>

  <div v-else-if="error" class="card">
    <h3>目录节点加载失败</h3>
    <p class="muted" style="margin-top:6px">{{ error }}</p>
    <p class="muted" style="margin-top:10px">
      请确认后端已启动（svc-catalog :8082 / BFF :8090），且已导入数据快照。
    </p>
    <button class="btn ghost sm" style="margin-top:12px" @click="load">重试</button>
  </div>

  <template v-else-if="d">
    <div class="nd-head">
      <div>
        <h1 v-if="!embedded" class="serif" style="font-size:30px">{{ d.node.title }}</h1>
        <h2 v-else class="serif" style="font-size:22px;margin-bottom:4px">{{ d.node.title }}</h2>
        <p class="muted" style="margin-top:6px">
          该节点下共 {{ d.childCount }} 个直接子节点 · {{ units.length }} 段原文 ·
          {{ d.formulas.length }} 个方剂 · {{ d.cases.length }} 则医案 ·
          {{ d.quotes.length }} 条相关条文
        </p>
      </div>
      <slot name="actions" />
    </div>

    <!-- 原文正文：按原书页序把知识单元的正文连排，尽量还原原书版面 -->
    <template v-if="units.length">
      <h2 class="section-title"><span class="dot"></span>原文</h2>
      <div class="unit-list">
        <article v-for="u in units" :key="u.id" class="unit">
          <div class="unit-head">
            <RouterLink v-if="u.refType === 'formula'" class="unit-title serif" :to="`/formula/${u.refId}`">
              {{ u.title }} ↗
            </RouterLink>
            <RouterLink v-else-if="u.refType === 'case'" class="unit-title serif" :to="`/case/${u.refId}`">
              {{ u.title }} ↗
            </RouterLink>
            <span v-else class="unit-title serif">{{ u.title }}</span>
            <span class="chip" style="font-size:11px">{{ refLabel(u.refType) }}</span>
            <span v-if="u.page" class="muted" style="font-size:12px">{{ u.page }}</span>
          </div>
          <p class="unit-body serif">{{ u.content }}</p>
        </article>
      </div>
    </template>

    <!-- 没有正文单元时退回摘要卡片（老数据 / 只在类节点上有的情况） -->
    <template v-else>
      <template v-if="d.formulas.length">
        <h2 class="section-title"><span class="dot"></span>本节点方剂</h2>
        <div class="grid cols-2">
          <RouterLink v-for="f in d.formulas" :key="f.id" class="rowitem" :to="`/formula/${f.id}`">
            <span class="thumb">{{ f.name.slice(0, 1) || '方' }}</span>
            <div>
              <b>{{ f.name }}</b>
              <div class="muted">
                {{ f.efficacy || f.syndrome || '证治待补录' }}
                <template v-if="f.page"> · 第 {{ f.page }} 页</template>
              </div>
            </div>
          </RouterLink>
        </div>
      </template>

      <template v-if="d.cases.length">
        <h2 class="section-title"><span class="dot"></span>相关医案</h2>
        <div style="display:grid;gap:10px">
          <RouterLink v-for="c in d.cases" :key="c.id" class="rowitem" :to="`/case/${c.id}`">
            <span class="thumb">案</span>
            <div>
              <b>{{ c.title || '医案' }}</b>
              <div class="muted">
                <template v-if="c.mainFormulaName">{{ c.mainFormulaName }}</template>
                <template v-if="c.mainFormulaName && c.page"> · </template>
                <template v-if="c.page">第 {{ c.page }} 页</template>
                <template v-if="!c.mainFormulaName && !c.page">暂无摘要</template>
              </div>
            </div>
          </RouterLink>
        </div>
      </template>
    </template>

    <template v-if="d.node.children.length">
      <h2 class="section-title"><span class="dot"></span>子节点</h2>
      <div class="grid cols-2 stagger">
        <!-- 用 a + 事件而不是 RouterLink：嵌在典籍页右侧时要原地切换，独立页面时才跳路由 -->
        <a v-for="c in d.node.children" :key="c.id" class="rowitem" @click="goChild(c.id)">
          <span class="thumb">{{ c.title.slice(0, 1) || '节' }}</span>
          <div>
            <b>{{ c.title }}</b>
            <div class="muted">{{ nodeTypeLabel(c.nodeType) }}</div>
          </div>
        </a>
      </div>
    </template>

    <template v-if="d.quotes.length">
      <h2 class="section-title"><span class="dot"></span>经典条文</h2>
      <div style="display:grid;gap:10px">
        <RouterLink
          v-for="q in d.quotes"
          :key="q.id + (q.articleNo ?? '')"
          class="cite"
          :to="`/quote/${q.id}`"
        >
          <div>
            <div>{{ excerpt(q.content || q.plainText) || '（原文待补录）' }}</div>
            <div class="pg">
              {{ q.label || q.classicName || '经典条文' }}
              <template v-if="q.page"> · 第 {{ q.page }} 页</template>
              · 查看条文 ↗
            </div>
          </div>
        </RouterLink>
      </div>
    </template>

    <div v-if="isEmpty" class="card" style="margin-top:18px">
      <p class="muted">该节点暂无内容（可能该分类尚未挂接方剂，或该节原文未收录）</p>
    </div>
  </template>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { getNodeContent, getNodeDetail, type NodeDetail, type UnitText } from '@/api/catalog'

/**
 * 单个目录节点的详情：**原文正文 + 子节点 + 条文**。
 *
 * 抽成组件的两层原因：
 * 1. 典籍页原先右侧只放"子单元卡片 + 打开详情按钮"，点一下整页跳走、右侧大半屏是空的；
 *    现在典籍页把它嵌在右侧，点目录就地换内容。
 * 2. 原来只渲染方剂/医案摘要卡片，原书里的讨论、按语、辨证立法这些正文根本看不到。
 *    实测原书 95.5% 的文字都在 content_unit 里，所以改成按页序把这些正文连排出来（即"原文"块）。
 *
 * embedded=true 时：标题降级为 h2、不显示自己的面包屑，子节点点击通过 `open` 事件交给父组件原地切换。
 */
const props = withDefaults(defineProps<{ id: string; embedded?: boolean }>(), {
  embedded: false
})
const emit = defineEmits<{ open: [id: string]; loaded: [detail: NodeDetail] }>()

const router = useRouter()
const d = ref<NodeDetail | null>(null)
const units = ref<UnitText[]>([])
const loading = ref(false)
const error = ref('')

const isEmpty = computed(
  () =>
    !!d.value &&
    !units.value.length &&
    !d.value.formulas.length &&
    !d.value.cases.length &&
    !d.value.quotes.length
)

const NODE_TYPE_LABEL: Record<string, string> = {
  chapter: '章',
  section: '节',
  category: '类方证'
}
const REF_LABEL: Record<string, string> = { formula: '方剂', case: '医案', node: '理论' }

function nodeTypeLabel(nodeType?: string): string {
  if (!nodeType) return '节点'
  return NODE_TYPE_LABEL[nodeType] ?? nodeType
}

function refLabel(refType: string): string {
  return REF_LABEL[refType] ?? refType
}

function excerpt(text?: string, max = 120): string {
  if (!text) return ''
  return text.length > max ? `${text.slice(0, max)}…` : text
}

function goChild(childId: string) {
  if (props.embedded) emit('open', childId)
  else router.push(`/node/${childId}`)
}

async function load() {
  if (!props.id) return
  loading.value = true
  error.value = ''
  try {
    // 正文与摘要并行取：正文失败不该让整页报错（老数据可能没有 content 接口数据）
    const [detail, content] = await Promise.all([
      getNodeDetail(props.id),
      getNodeContent(props.id).catch(() => null)
    ])
    d.value = detail
    units.value = content?.units ?? []
    emit('loaded', detail)
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载失败'
    d.value = null
    units.value = []
  } finally {
    loading.value = false
  }
}

watch(() => props.id, load)
onMounted(load)
</script>

<style scoped>
.nd-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  flex-wrap: wrap;
}

.unit-list {
  display: grid;
  gap: 18px;
  margin-bottom: 8px;
}

.unit {
  border-left: 3px solid rgba(47, 106, 79, 0.25);
  padding-left: 14px;
}

.unit-head {
  display: flex;
  align-items: baseline;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 6px;
}

.unit-title {
  font-weight: 700;
  font-size: 16px;
  color: var(--primary-deep, #2f6a4f);
  text-decoration: none;
}

.unit-body {
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.85;
  font-size: 14.5px;
  color: #333;
  margin: 0;
}
</style>
