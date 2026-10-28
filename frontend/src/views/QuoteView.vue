<template>
  <div class="crumb">
    <RouterLink to="/">首页</RouterLink> /
    <RouterLink to="/library">典籍</RouterLink> /
    <template v-if="q?.bookTitle">{{ q.bookTitle }} / </template>
    条文
  </div>

  <div v-if="loading" class="card"><p class="muted">加载中…</p></div>

  <div v-else-if="error" class="card">
    <h3>条文加载失败</h3>
    <p class="muted" style="margin-top:6px">{{ error }}</p>
  </div>

  <div v-else-if="q" class="grid" style="grid-template-columns:1fr 320px">
    <section class="card">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px">
        <div>
          <h1 class="serif" style="font-size:26px">
            {{ q.label || (q.classicName ? `《${q.classicName}》` : '条文') }}
          </h1>
          <div class="muted">
            <template v-if="q.classicName">《{{ q.classicName }}》</template>
            <template v-if="q.page"> · 第 {{ q.page }} 页</template>
            <template v-if="q.articleNo"> · 条文编号 {{ q.articleNo }}</template>
            <template v-if="!q.page && !q.articleNo"> · 页码与编号未收录</template>
          </div>
        </div>
        <div style="display:flex;gap:8px">
          <button class="btn ghost sm" @click="onFav">★ 收藏</button>
          <button class="btn ghost sm" @click="noteOpen = true">✎ 笔记</button>
        </div>
      </div>
      <div class="hr"></div>

      <h3 style="margin-bottom:10px">原文</h3>
      <blockquote
        v-for="it in q.items"
        :key="(it.no || 'x') + it.text.slice(0, 8)"
        class="cite"
        :id="it.no ? `no-${it.no}` : undefined"
        :style="[
          { marginBottom: '10px', display: 'block', fontFamily: `'Noto Serif SC',serif`, fontSize: '15.5px', lineHeight: 2 },
          it.no && it.no === activeNo ? { borderLeftColor: 'var(--primary)', background: 'var(--primary-soft)' } : {}
        ]"
      >
        <div>
          <span v-if="it.no" class="chip" style="margin-right:8px;font-size:11px">第 {{ it.no }} 条</span>
          {{ it.text }}
        </div>
      </blockquote>

      <h3 style="margin:20px 0 10px">
        白话释义 <span class="chip" style="font-size:11px">AI 辅助</span>
      </h3>
      <p v-if="q.plainText" style="line-height:1.9">{{ q.plainText }}</p>
      <p v-else class="muted">本条暂无白话释义（可由域3 Agent 生成后回填 plain_text）。</p>

      <div class="hr"></div>
      <h3 style="margin-bottom:10px">条文反向索引</h3>
      <div class="muted" style="margin-bottom:10px">引用本条的方剂与医案：</div>

      <RouterLink
        v-for="f in q.formulas"
        :key="'f' + f.id"
        class="rowitem"
        :to="`/formula/${f.id}`"
        style="margin-bottom:10px"
      >
        <span class="thumb">{{ f.name.slice(0, 1) }}</span>
        <div>
          <b>{{ f.name }}</b>
          <div class="muted">方剂 · 条文所主</div>
        </div>
      </RouterLink>

      <RouterLink
        v-for="c in q.cases"
        :key="'c' + c.id"
        class="rowitem"
        :to="`/case/${c.id}`"
        style="margin-bottom:10px"
      >
        <span class="thumb">案</span>
        <div>
          <b>{{ c.name }}</b>
          <div class="muted">医案 · 应用本案条文</div>
        </div>
      </RouterLink>

      <p v-if="!q.formulas.length && !q.cases.length" class="muted">
        暂无关联的方剂或医案（关系表待 ETL 补齐，或用检索页按方名反查）。
      </p>
    </section>

    <aside style="display:grid;gap:16px;align-self:start">
      <div class="card">
        <h3 style="font-size:15px;margin-bottom:10px">同篇条文</h3>
        <p class="muted" style="font-size:13px;margin-bottom:8px">
          本页共 {{ q.items.length }} 条原文，点击定位：
        </p>
        <div style="max-height:280px;overflow:auto">
          <button
            v-for="it in q.items"
            :key="'t' + (it.no || it.text.slice(0, 6))"
            class="rowitem"
            style="width:100%;text-align:left;padding:8px 10px;margin-bottom:6px;background:none"
            @click="focusItem(it.no)"
          >
            <span class="thumb" style="width:34px;height:34px;font-size:12px">{{ it.no || '条' }}</span>
            <div class="muted" style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">
              {{ it.text.slice(0, 40) }}
            </div>
          </button>
        </div>
      </div>

      <div class="card">
        <h3 style="font-size:15px;margin-bottom:8px">背诵打卡</h3>
        <p class="muted" style="font-size:13px">加入背诵计划后按 SRS 复习（域2 提供）。</p>
        <button class="btn primary sm" style="margin-top:10px" @click="onRecite">加入背诵计划</button>
      </div>

      <div class="card">
        <h3 style="font-size:15px;margin-bottom:6px">问 Agent</h3>
        <p class="muted" style="margin-bottom:10px">“本条为何用此方？”</p>
        <RouterLink class="btn primary sm" to="/ask">去问 Agent →</RouterLink>
      </div>
    </aside>
  </div>

  <NoteDrawer
    :open="noteOpen"
    :title="`写笔记 · ${q?.label || '条文'}`"
    :storage-key="`note:quote:${id}`"
    @close="noteOpen = false"
  />
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { getQuote, type QuoteDetail } from '@/api/catalog'
import NoteDrawer from '@/components/NoteDrawer.vue'
import { toast } from '@/utils/toast'

const route = useRoute()
const id = computed(() => String(route.params.id))
const activeNo = computed(() => (route.query.no ? String(route.query.no) : ''))

const q = ref<QuoteDetail | null>(null)
const loading = ref(false)
const error = ref('')
const noteOpen = ref(false)

async function load() {
  loading.value = true
  error.value = ''
  try {
    q.value = await getQuote(id.value)
    if (activeNo.value) {
      await nextTick()
      document.getElementById(`no-${activeNo.value}`)?.scrollIntoView({ block: 'center', behavior: 'smooth' })
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载失败'
    q.value = null
  } finally {
    loading.value = false
  }
}

function focusItem(no?: string) {
  if (!no) return
  document.getElementById(`no-${no}`)?.scrollIntoView({ block: 'center', behavior: 'smooth' })
}

function onFav() {
  toast('收藏需登录（域2 的收藏接口待接入）')
  if (q.value) localStorage.setItem(`fav:quote:${q.value.id}`, '1')
}

function onRecite() {
  toast('已加入背诵计划（本地暂存，域2 接入后同步）')
}

watch(id, load)
onMounted(load)
</script>
