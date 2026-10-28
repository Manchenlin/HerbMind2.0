<template>
  <div class="crumb">
    <RouterLink to="/">首页</RouterLink> /
    <RouterLink to="/library">典籍</RouterLink> /
    <template v-if="f?.bookTitle">{{ f.bookTitle }} / </template>
    <template v-if="f?.chapter">{{ f.chapter }} / </template>
    {{ f?.name || id }}
  </div>

  <div v-if="loading" class="card"><p class="muted">加载中…</p></div>

  <div v-else-if="error" class="card">
    <h3>方剂加载失败</h3>
    <p class="muted" style="margin-top:6px">{{ error }}</p>
    <p class="muted" style="margin-top:10px">
      请确认后端已启动（svc-catalog :8082 / BFF :8090），且已导入数据快照。
    </p>
  </div>

  <div v-else-if="f" class="grid" style="grid-template-columns:210px 1fr 300px">
    <!-- 左：目录 -->
    <aside class="card" style="align-self:start;font-size:14px">
      <div class="muted" style="margin-bottom:8px">目录</div>
      <div style="line-height:2">
        <div style="color:var(--text-2)">{{ f.bookTitle || '语料' }}</div>
        <div style="padding-left:10px">{{ f.chapter || '—' }}</div>
        <RouterLink
          v-if="f.nodeId"
          :to="`/node/${f.nodeId}`"
          style="padding-left:20px;font-weight:700;color:var(--primary-deep);display:block"
        >· {{ f.nodeTitle || '所属分类' }}</RouterLink>
        <div v-else style="padding-left:20px;font-weight:700;color:var(--primary-deep)">
          · {{ f.nodeTitle || '未归类' }}
        </div>
        <div style="padding-left:30px">{{ f.name }}</div>
        <RouterLink
          v-for="r in f.related"
          :key="r.id"
          :to="`/formula/${r.id}`"
          style="padding-left:30px;display:block;color:var(--text-2)"
        >（{{ r.name }}）</RouterLink>
      </div>
    </aside>

    <!-- 中：正文 -->
    <section class="card">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px">
        <div>
          <h1 class="serif" style="font-size:30px">{{ f.name }}</h1>
          <div class="muted">
            <template v-if="f.pinyin">{{ f.pinyin }} · </template>
            <template v-if="f.classicName">《{{ f.classicName }}》· </template>
            <template v-if="f.page">第 {{ f.page }} 页</template>
            <template v-if="!f.page">页码未收录</template>
          </div>
          <div v-if="f.alias" class="muted" style="margin-top:4px">别名：{{ f.alias }}</div>
        </div>
        <div style="display:flex;gap:8px;flex-wrap:wrap">
          <button class="btn ghost sm" @click="onFav">★ 收藏</button>
          <button class="btn ghost sm" @click="noteOpen = true">✎ 笔记</button>
        </div>
      </div>

      <div class="hr"></div>
      <div class="muted" style="margin-bottom:8px">组成</div>
      <div style="margin-bottom:18px">
        <HerbChips :herbs="f.herbs" />
        <p v-if="!f.herbs.length" class="muted" style="font-size:12.5px;margin-top:6px">
          原书未收录本方组成（快照里 245 方中 59 方无药味明细），可在治理后台补录。
        </p>
      </div>

      <div class="grid cols-2" style="gap:14px;margin-bottom:18px">
        <div>
          <div class="muted">功效</div>
          <div style="margin-top:4px">{{ f.efficacy || '未收录（可在治理后台补录）' }}</div>
        </div>
        <div>
          <div class="muted">主治证候</div>
          <div style="margin-top:4px">{{ f.syndrome || '未收录' }}</div>
        </div>
      </div>

      <h3 style="margin:6px 0 10px">原文回顾</h3>
      <template v-if="f.quotes.length">
        <RouterLink
          v-for="q in f.quotes"
          :key="q.id + (q.articleNo || '')"
          class="cite"
          style="margin-bottom:10px;display:flex"
          :to="`/quote/${q.id}`"
        >
          <div>
            <div>{{ q.content }}</div>
            <div class="pg">{{ q.label || q.classicName }} <template v-if="q.page">· 第 {{ q.page }} 页</template> · 条文详情 ↗</div>
          </div>
        </RouterLink>
      </template>
      <p v-else class="muted">未在已接入经典原文中检索到直接引用本方的条文。</p>

      <div class="hr"></div>

      <div class="reveal" :class="{ show: expanded }">
        <h3 style="margin:6px 0 10px">证治归纳</h3>
        <p class="muted" style="white-space:pre-wrap">{{ f.sourceText || f.syndrome || '原文未收录本方「证治归纳」段落。' }}</p>
        <h3 style="margin:14px 0 10px">使用提示</h3>
        <p class="muted">
          本方组成与剂量以原书为准；临床使用需辨证加减，表虚有汗、阴虚火旺者慎用。
          剂量单位与古今换算见《方剂学》教材。
        </p>
      </div>
      <div v-if="!expanded" class="mask"></div>
      <button v-if="!expanded" class="btn ghost sm" @click="expanded = true">展开更多栏目（渐进阅读）</button>

      <div class="hr"></div>
      <h3 style="margin:6px 0 10px">相关医案</h3>
      <div v-if="f.cases.length" class="stagger" style="display:grid;gap:10px">
        <RouterLink v-for="c in f.cases" :key="c.id" class="rowitem" :to="`/case/${c.id}`">
          <span class="thumb">案</span>
          <div>
            <b>{{ c.title || '医案' }}</b>
            <div class="muted">
              <template v-if="c.page">第 {{ c.page }} 页</template>
              <template v-else>页码未收录</template>
            </div>
          </div>
        </RouterLink>
      </div>
      <p v-else class="muted">暂无关联医案。</p>
    </section>

    <!-- 右：关联 -->
    <aside style="display:grid;gap:16px;align-self:start">
      <div class="card">
        <div style="display:flex;justify-content:space-between;align-items:center">
          <h3 style="font-size:15px">关系图谱</h3>
          <RouterLink class="chip clickable" :to="`/graph?entity=${encodeURIComponent(f.name)}`">展开 ↗</RouterLink>
        </div>
        <MiniGraph :graph="graph" :w="260" :h="180" @pick="onPick" />
        <p class="muted" style="font-size:12.5px">方-药-证 关系预览（内容域轻量版）</p>
      </div>

      <div class="card">
        <h3 style="font-size:15px;margin-bottom:10px">相似 / 加减方</h3>
        <RouterLink
          v-for="r in f.related"
          :key="r.id"
          class="rowitem"
          :to="`/formula/${r.id}`"
          style="padding:10px;margin-bottom:8px"
        >
          <span class="thumb" style="width:36px;height:36px;font-size:13px">{{ r.name.slice(0, 1) }}</span>
          <div>
            <b>{{ r.name }}</b>
            <div class="muted">{{ r.efficacy || '同章节方证' }}</div>
          </div>
        </RouterLink>
        <p v-if="!f.related.length" class="muted">暂无同类方剂。</p>
      </div>

      <div class="card">
        <h3 style="font-size:15px;margin-bottom:6px">AI 追问</h3>
        <p class="muted" style="margin-bottom:10px">“{{ f.name }}的加减规律与禁忌？”</p>
        <RouterLink class="btn primary sm" to="/ask">去问 Agent →</RouterLink>
      </div>
    </aside>
  </div>

  <NoteDrawer
    :open="noteOpen"
    :title="`写笔记 · ${f?.name || ''}`"
    :storage-key="`note:formula:${id}`"
    @close="noteOpen = false"
  />
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getFormula, type FormulaDetail } from '@/api/catalog'
import type { GraphPreview } from '@/api/home'
import HerbChips from '@/components/HerbChips.vue'
import MiniGraph from '@/components/MiniGraph.vue'
import NoteDrawer from '@/components/NoteDrawer.vue'
import { toast } from '@/utils/toast'

const route = useRoute()
const router = useRouter()
const id = computed(() => String(route.params.id))

const f = ref<FormulaDetail | null>(null)
const loading = ref(false)
const error = ref('')
const expanded = ref(false)
const noteOpen = ref(false)

const graph = computed<GraphPreview | null>(() => {
  if (!f.value) return null
  const center = `f:${f.value.id}`
  const nodes = [{ id: center, type: 'Formula', name: f.value.name, level: 0 }]
  const edges: GraphPreview['edges'] = []
  for (const h of f.value.herbs) {
    const hid = `h:${h.name}`
    nodes.push({ id: hid, type: 'Herb', name: h.name, level: 1 })
    edges.push({ source: center, target: hid, rel: 'COMPOSED_OF' })
  }
  if (f.value.syndrome) {
    const sid = `s:${f.value.id}`
    nodes.push({ id: sid, type: 'Syndrome', name: f.value.syndrome.slice(0, 8), level: 1 })
    edges.push({ source: center, target: sid, rel: 'INDICATES' })
  }
  return { nodes, edges, formulaId: f.value.id }
})

async function load() {
  loading.value = true
  error.value = ''
  try {
    f.value = await getFormula(id.value)
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载失败'
    f.value = null
  } finally {
    loading.value = false
  }
}

function onFav() {
  toast('收藏需登录（域2 的 /api/biz/user/favorite 待接入）')
  if (f.value) localStorage.setItem(`fav:formula:${f.value.id}`, '1')
}

function onPick(node: { id: string; type: string; name: string }) {
  if (node.type === 'Formula' && f.value && node.id === `f:${f.value.id}`) return
  if (node.type === 'Herb') router.push({ path: '/search', query: { herb: node.name } })
}

watch(id, load)
onMounted(load)
</script>
