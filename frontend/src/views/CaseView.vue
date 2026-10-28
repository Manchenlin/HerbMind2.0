<template>
  <div class="crumb">
    <RouterLink to="/">首页</RouterLink> /
    <RouterLink to="/library">典籍</RouterLink> /
    <template v-if="c?.bookTitle">{{ c.bookTitle }} / </template>
    <template v-if="c?.chapter">{{ c.chapter }} / </template>
    <template v-if="c?.mainFormulaId">
      <RouterLink :to="`/formula/${c.mainFormulaId}`">{{ c.mainFormulaName || '主方' }}</RouterLink> /
    </template>
    医案
  </div>

  <div v-if="loading" class="card"><p class="muted">加载中…</p></div>

  <div v-else-if="error" class="card">
    <h3>医案加载失败</h3>
    <p class="muted" style="margin-top:6px">{{ error }}</p>
    <p class="muted" style="margin-top:10px">请确认 svc-catalog 与 BFF 已启动，且数据快照已导入。</p>
  </div>

  <template v-else-if="c">
    <h1 class="serif" style="margin-bottom:6px">{{ c.title || '医案' }}</h1>
    <div class="muted" style="margin-bottom:16px">
      主方
      <RouterLink v-if="c.mainFormulaId" :to="`/formula/${c.mainFormulaId}`" style="color:var(--primary)">
        {{ c.mainFormulaName || c.mainFormulaId }}
      </RouterLink>
      <span v-else>未关联方剂</span>
      <template v-if="c.page"> · 第 {{ c.page }} 页</template>
      <template v-if="c.syndrome"> · {{ c.syndrome }}</template>
    </div>

    <!-- 案例一 / 二 / 三：同一主方下的其它医案 -->
    <div v-if="caseTabs.length > 1" class="pill-tabs" style="margin-bottom:10px">
      <button
        v-for="(t, i) in caseTabs"
        :key="t.id"
        :class="{ active: t.id === c.id }"
        :title="t.title"
        @click="openCase(t.id)"
      >案例{{ caseLabel(i) }}</button>
    </div>

    <div class="pill-tabs" style="margin-bottom:18px">
      <button :class="{ active: tab === 'main' }" @click="tab = 'main'">案例原文</button>
      <button :class="{ active: tab === 'comment' }" @click="tab = 'comment'">
        按语 · 讨论<template v-if="comment">（{{ comment.length }}）</template>
      </button>
      <button :class="{ active: tab === 'quotes' }" @click="tab = 'quotes'">
        相关条文<template v-if="c.quotes.length">（{{ c.quotes.length }}）</template>
      </button>
    </div>

    <div class="grid" style="grid-template-columns:1fr 300px">
      <section class="card">
        <!-- 案例原文 -->
        <template v-if="tab === 'main'">
          <template v-if="blocks.length">
            <div v-for="b in visibleBlocks" :key="b.label" style="margin-bottom:16px">
              <h3 style="margin-bottom:8px">{{ b.label }}</h3>
              <p style="white-space:pre-wrap;line-height:1.9">{{ b.content }}</p>
            </div>

            <template v-if="answerBlocks.length">
              <div class="hr"></div>
              <div class="reveal" :class="{ show: revealed }">
                <div v-for="b in answerBlocks" :key="b.label" style="margin-bottom:16px">
                  <h3 style="margin-bottom:8px">{{ b.label }}</h3>
                  <p style="white-space:pre-wrap;line-height:1.9">{{ b.content }}</p>
                </div>
              </div>
              <div v-if="!revealed" class="mask"></div>
              <div style="display:flex;gap:10px;margin-top:6px;flex-wrap:wrap">
                <button v-if="!revealed" class="btn accent" @click="reveal">揭晓原著答案</button>
                <button v-else class="btn ghost sm" disabled>已揭晓原著答案 ✓</button>
                <RouterLink class="btn ghost" to="/train">先思后看 · 我来辨证</RouterLink>
              </div>
            </template>
          </template>
          <p v-else class="muted">该医案暂无正文栏目。</p>
        </template>

        <!-- 按语 -->
        <template v-else-if="tab === 'comment'">
          <template v-if="comment.length">
            <div v-for="s in comment" :key="s.id" style="margin-bottom:16px">
              <h3 style="margin-bottom:8px">{{ s.kind || '按语' }}</h3>
              <p class="muted" style="white-space:pre-wrap;line-height:1.9">{{ s.content }}</p>
            </div>
          </template>
          <p v-else class="muted">该医案暂无按语。</p>
          <div class="hr"></div>
          <h3 style="margin-bottom:8px">讨论</h3>
          <p class="muted">讨论区由域2（用户域）提供，接入后此处展示楼层与回复。</p>
        </template>

        <!-- 相关条文 -->
        <template v-else>
          <template v-if="c.quotes.length">
            <RouterLink
              v-for="q in c.quotes"
              :key="q.id + (q.articleNo || '')"
              class="cite"
              style="margin-bottom:10px;display:flex"
              :to="`/quote/${q.id}`"
            >
              <div>
                <div>{{ q.content }}</div>
                <div class="pg">{{ q.label || q.classicName }} · 条文详情 ↗</div>
              </div>
            </RouterLink>
          </template>
          <p v-else class="muted">未检索到与本案主方直接关联的条文。</p>
        </template>
      </section>

      <aside style="display:grid;gap:16px;align-self:start">
        <div class="card">
          <h3 style="font-size:15px;margin-bottom:8px">辨证要点</h3>
          <p class="muted">{{ c.syndrome || '原书未单列舌脉/证候字段。' }}</p>
        </div>

        <div class="card">
          <h3 style="font-size:15px;margin-bottom:8px">关联方剂</h3>
          <RouterLink v-if="c.mainFormulaId" class="rowitem" :to="`/formula/${c.mainFormulaId}`" style="padding:10px">
            <span class="thumb" style="width:36px;height:36px;font-size:13px">
              {{ (c.mainFormulaName || '方').slice(0, 1) }}
            </span>
            <div>
              <b>{{ c.mainFormulaName || '主方' }}</b>
              <div class="muted">查看组成与条文</div>
            </div>
          </RouterLink>
          <p v-else class="muted">未关联方剂。</p>
        </div>

        <div class="card">
          <h3 style="font-size:15px;margin-bottom:6px">问 Agent</h3>
          <p class="muted" style="margin-bottom:10px">“{{ c.title }}为何这样辨证？”</p>
          <RouterLink class="btn primary sm" to="/ask">去问 Agent →</RouterLink>
        </div>
      </aside>
    </div>
  </template>

  <div v-else class="card"><p class="muted">未找到该医案。</p></div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getCase, type CaseBrief, type CaseDetail, type CaseSection } from '@/api/catalog'
import { isAnswerBlock, parseCaseText, type CaseBlock } from '@/utils/format'
import { toast } from '@/utils/toast'

const route = useRoute()
const router = useRouter()
const id = computed(() => String(route.params.id))

const c = ref<CaseDetail | null>(null)
const loading = ref(false)
const error = ref('')
const tab = ref<'main' | 'comment' | 'quotes'>('main')
const revealed = ref(false)

/** 同一主方下的案例：当前 + siblings，按 id 排序后固定编号「案例一/二/三」 */
const caseTabs = computed<Array<Pick<CaseBrief, 'id' | 'title'>>>(() => {
  if (!c.value) return []
  const self = { id: c.value.id, title: c.value.title || '医案' }
  return [self, ...(c.value.siblings ?? [])].sort((a, b) =>
    a.id.localeCompare(b.id, undefined, { numeric: true })
  )
})

const CN_NUM = ['一', '二', '三', '四', '五', '六', '七', '八', '九']

function caseLabel(index: number): string {
  return CN_NUM[index] ?? String(index + 1)
}

function openCase(caseId: string) {
  if (caseId !== c.value?.id) router.push(`/case/${caseId}`)
}

const mainSection = computed<CaseSection | undefined>(() =>
  c.value?.sections.find((s) => (s.kind || '').includes('原文'))
)
const comment = computed<CaseSection[]>(() =>
  (c.value?.sections ?? []).filter((s) => !(s.kind || '').includes('原文'))
)
const blocks = computed<CaseBlock[]>(() => parseCaseText(mainSection.value?.content))
const visibleBlocks = computed(() => blocks.value.filter((b) => !isAnswerBlock(b.label)))
const answerBlocks = computed(() => blocks.value.filter((b) => isAnswerBlock(b.label)))

async function load() {
  loading.value = true
  error.value = ''
  revealed.value = false
  try {
    c.value = await getCase(id.value)
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载失败'
    c.value = null
  } finally {
    loading.value = false
  }
}

function reveal() {
  revealed.value = true
  toast('已揭晓原著答案')
}

watch(id, load)
onMounted(load)
</script>
