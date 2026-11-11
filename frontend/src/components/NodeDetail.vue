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
          该节点下共 {{ d.childCount }} 个直接子节点<template v-if="units.length">
            · {{ units.length }} 段原文</template> · {{ d.formulas.length }} 个方剂 ·
          {{ d.cases.length }} 则医案 · {{ d.quotes.length }} 条相关条文
        </p>
      </div>
      <slot name="actions" />
    </div>

    <!-- 章级不拉正文：整章可能 239 段、16 万字、近 500 KB，让用户先在目录里选节 -->
    <p v-if="skipChapterText" class="muted" style="margin:12px 0 0">
      本章共 {{ d.childCount }} 节，请从下方「子节点」或左侧目录选一节阅读原文。
      <span style="opacity:.75">（整章正文往往上百段、十几万字，一次加载会明显卡顿，故按节阅读）</span>
    </p>

    <!-- 原文正文：按原书页序把知识单元的正文连排，尽量还原原书版面 -->
    <template v-if="shownUnits.length">
      <h2 class="section-title"><span class="dot"></span>原文</h2>
      <div class="unit-list">
        <article v-for="u in shownUnits" :key="u.id" class="unit">
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
          <p class="unit-body serif">
            <!-- 正文里出现的本节方剂名做成可悬浮词条：悬停看组成，点击进完整条目 -->
            <template v-for="(seg, si) in segmentsOf(u)" :key="si">
              <span
                v-if="seg.formula"
                class="term"
                @mouseenter="showCard(seg.formula, $event)"
                @mouseleave="hideCard"
                @click="openFormula(seg.formula)"
              >{{ seg.text }}</span>
              <span v-else>{{ seg.text }}</span>
            </template>
          </p>
        </article>
      </div>
      <!-- 分批渲染：段数多的节先渲染前若干段，避免一次性挂载几十万字 DOM -->
      <div v-if="hasMore" style="margin:16px 0 4px">
        <button class="btn ghost sm" @click="showMore">
          继续阅读（剩 {{ units.length - visibleCount }} 段）
        </button>
        <span class="muted" style="margin-left:10px;font-size:12px">
          已显示 {{ visibleCount }} / {{ units.length }} 段
        </span>
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

  <!-- 方名悬浮卡：Teleport 到 body，避免被阅读区的 overflow / 变换裁掉 -->
  <Teleport to="body">
    <div v-if="hoverFormula" class="term-card" :style="cardStyle">
      <div class="tc-head">
        <b>{{ hoverFormula.name }}</b>
        <span v-if="hoverFormula.page" class="muted">{{ hoverFormula.page }}</span>
      </div>
      <p v-if="hoverFormula.efficacy" class="tc-line">功效：{{ hoverFormula.efficacy }}</p>
      <p v-if="hoverFormula.syndrome" class="tc-line">主治：{{ hoverFormula.syndrome }}</p>
      <p v-if="herbText(hoverFormula)" class="tc-line">组成：{{ herbText(hoverFormula) }}</p>
      <p class="tc-tip muted">点方名可查看完整条目</p>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  getNodeContent,
  getNodeDetail,
  type FormulaBrief,
  type NodeDetail,
  type UnitText
} from '@/api/catalog'

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

/**
 * 分批渲染的每批段数。
 *
 * 实测数据（2026-11-11，第四章）：整章 20 节共 239 段、16.2 万字、接口返回约 489 KB；
 * 单节最大 26 段、1.6 万字 —— 节级本身够轻，卡顿主要来自章级一次拉整章。
 * 所以主措施是章级不拉正文（见 skipChapterText），分批只作兜底：
 * 换更大的书、或某节突然塞进上百段时，不至于一次性挂载几十万字 DOM。
 */
const BATCH_SIZE = 40
const visibleCount = ref(BATCH_SIZE)

/** 当前节点是「章」层：章下通常有节，整章正文过重，默认按节阅读 */
const isChapter = computed(() => d.value?.node.nodeType === 'chapter')

/**
 * 章级且有子节点 => 不拉正文。
 * 章下没有子节点时不能跳（否则这一章的正文永远看不到），照常整章加载 + 分批渲染。
 */
const skipChapterText = computed(() => isChapter.value && (d.value?.node.children.length ?? 0) > 0)

/** 当前批次要渲染的正文 */
const shownUnits = computed(() => units.value.slice(0, visibleCount.value))
const hasMore = computed(() => visibleCount.value < units.value.length)

function showMore() {
  visibleCount.value += BATCH_SIZE
}

const isEmpty = computed(
  () =>
    !!d.value &&
    !skipChapterText.value &&
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
  visibleCount.value = BATCH_SIZE
  try {
    // 先取摘要（体积小），再决定要不要拉正文：章级整章正文可达数百 KB，不预取
    const detail = await getNodeDetail(props.id)
    d.value = detail

    const needsText = !(detail.node.nodeType === 'chapter' && detail.node.children.length > 0)
    if (needsText) {
      // 正文失败不该让整页报错（老数据可能没有 content 接口数据）
      const content = await getNodeContent(props.id).catch(() => null)
      units.value = content?.units ?? []
    } else {
      units.value = []
    }
    emit('loaded', detail)
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载失败'
    d.value = null
    units.value = []
  } finally {
    loading.value = false
  }
}

/* ===== 方名悬浮卡片 ===== */

interface TextSegment {
  text: string
  formula?: FormulaBrief
}

const hoverFormula = ref<FormulaBrief | null>(null)
const cardPos = ref({ left: 0, top: 0 })

/** 触屏没有 hover，点击直接跳转方剂页（不弹卡片） */
const canHover = typeof window !== 'undefined' && window.matchMedia('(hover: hover)').matches

const cardStyle = computed(() => ({
  left: `${cardPos.value.left}px`,
  top: `${cardPos.value.top}px`
}))

/** 本节方剂名 → 方剂，供正文切分用；长名优先，避免「桂枝汤」抢走「桂枝加桂汤」 */
const formulaIndex = computed(() => {
  const map = new Map<string, FormulaBrief>()
  for (const f of d.value?.formulas ?? []) {
    if (f.name && f.name.length >= 2 && !map.has(f.name)) map.set(f.name, f)
  }
  return map
})

const formulaNames = computed(() => [...formulaIndex.value.keys()].sort((a, b) => b.length - a.length))

function splitByFormulas(text: string): TextSegment[] {
  const names = formulaNames.value
  if (!names.length || !text) return [{ text }]
  const out: TextSegment[] = []
  let buf = ''
  let i = 0
  outer: while (i < text.length) {
    for (const n of names) {
      if (text.startsWith(n, i)) {
        if (buf) {
          out.push({ text: buf })
          buf = ''
        }
        out.push({ text: n, formula: formulaIndex.value.get(n) })
        i += n.length
        continue outer
      }
    }
    buf += text[i]
    i++
  }
  if (buf) out.push({ text: buf })
  return out
}

/** 正文切分结果缓存：几十段 × 上千字，不缓存会在每次滚动/重渲染时白算 */
const segmentMap = computed(() => {
  const m = new Map<string, TextSegment[]>()
  for (const u of units.value) m.set(u.id, splitByFormulas(u.content))
  return m
})

function segmentsOf(u: UnitText): TextSegment[] {
  return segmentMap.value.get(u.id) ?? [{ text: u.content }]
}

function herbText(f: FormulaBrief): string {
  return (f.herbs ?? [])
    .map((h) => `${h.name}${h.dose ? ` ${h.dose}${h.unit || 'g'}` : ''}`)
    .join('、')
}

function showCard(f: FormulaBrief | undefined, e: MouseEvent) {
  if (!f || !canHover) return
  hoverFormula.value = f
  const w = 300
  const pad = 12
  const x = Math.min(e.clientX + 14, window.innerWidth - w - pad)
  const wantUp = e.clientY + 200 > window.innerHeight
  const y = wantUp ? Math.max(pad, e.clientY - 180) : e.clientY + 18
  cardPos.value = { left: Math.max(pad, x), top: y }
}

function hideCard() {
  hoverFormula.value = null
}

function openFormula(f: FormulaBrief | undefined) {
  if (!f) return
  hideCard()
  void router.push(`/formula/${f.id}`)
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
  /* 阅读页可切换主题，夜间模式要换成更亮的强调色 */
  color: var(--reader-accent, var(--primary-deep, #2f6a4f));
  text-decoration: none;
}

.unit-body {
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.85;
  /* 字号与前景色由阅读页（LibraryView 的 reader-pane）通过 CSS 变量下发 */
  font-size: var(--reader-font, 14.5px);
  color: var(--reader-fg, #333);
  margin: 0;
}

/* 正文中的方名：虚线下划线提示可点，悬停变底色 */
.term {
  border-bottom: 1px dashed var(--reader-accent, #2f6a4f);
  cursor: pointer;
  transition: background 0.14s ease;
}

.term:hover {
  background: rgba(47, 106, 79, 0.1);
}

/* 悬浮卡：fixed 定位到鼠标附近，由 Teleport 挂到 body 下 */
.term-card {
  position: fixed;
  z-index: 999;
  width: 300px;
  padding: 12px 14px;
  border: 1px solid #dde7e2;
  border-radius: 10px;
  background: #fff;
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.12);
  font-size: 13px;
  line-height: 1.65;
  color: #333;
  pointer-events: none;
}

.tc-head {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 6px;
  font-size: 14px;
}

.tc-line {
  margin: 0;
}

.tc-tip {
  margin: 8px 0 0;
  font-size: 11.5px;
}
</style>
