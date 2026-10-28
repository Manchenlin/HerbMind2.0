<template>
  <div class="crumb">
    <RouterLink to="/">首页</RouterLink> /
    <RouterLink to="/shelf">书架</RouterLink> /
    导入语料
  </div>

  <h1 class="serif" style="margin-bottom:6px">导入语料</h1>
  <p class="muted" style="margin-bottom:18px">
    把你自己的书籍 / 资料接入平台（UGC）。提交后进入治理审核，通过即可检索、问答、练习、建图。
  </p>

  <div class="steps">
    <div v-for="(s, i) in steps" :key="s" class="st" :class="{ on: submitted || i < 2 }">
      <span class="no">{{ i + 1 }}</span>{{ s }}
    </div>
  </div>

  <div class="grid" style="grid-template-columns:1fr 320px;align-items:start">
    <div style="display:grid;gap:16px;min-width:0">
      <!-- 提交结果 -->
      <section v-if="result" class="card" style="border-color:#CDE6DF">
        <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">
          <span class="badge ok">已提交</span>
          <h3 style="margin:0">{{ result.status || '待复核' }}</h3>
        </div>
        <div class="muted" style="margin-top:8px">
          导入单号：<span class="mono">{{ result.importId }}</span>
          <template v-if="result.createdAt"> · {{ result.createdAt }}</template>
        </div>
        <p class="muted" style="margin-top:6px">
          {{ result.message || '已登记语料元信息，等待治理审核。' }}
        </p>
        <p v-if="statusError" class="muted" style="margin-top:8px;color:#A32D2D">
          状态查询失败：{{ statusError }}
        </p>
        <button
          class="btn ghost sm"
          style="margin-top:12px"
          :disabled="statusLoading"
          @click="refreshStatus"
        >{{ statusLoading ? '查询中…' : '查看导入状态' }}</button>
      </section>

      <!-- 尚未提交（空态） -->
      <p v-else class="muted">
        尚未提交导入单：填写下方信息并点击「提交导入」，系统会生成导入单号供你追踪审核进度。
      </p>

      <!-- 表单 -->
      <form class="card" @submit.prevent="onSubmit">
        <div
          class="dropzone"
          role="button"
          tabindex="0"
          @click="onDropzone"
          @keydown.enter.prevent="onDropzone"
        >
          <div class="ic">⬆</div>
          <div style="margin-top:6px"><b>拖拽文件到此处，或点击上传</b></div>
          <div class="hint">支持 .docx / .txt / .md / .csv，单文件 ≤ 50MB</div>
        </div>

        <div class="hr"></div>

        <h3 style="margin-bottom:12px">语料信息</h3>
        <div class="grid cols-2" style="gap:14px">
          <div class="field">
            <label for="import-title">书名 *</label>
            <input id="import-title" v-model="form.title" class="input" placeholder="如：伤寒论注">
          </div>
          <div class="field">
            <label for="import-type">类型 *</label>
            <select id="import-type" v-model="form.bookType" class="input">
              <option value="fz">方证书（方剂 / 条文 / 医案）</option>
              <option value="bencao">本草书（药材专论）</option>
              <option value="drug">药品书（中成药 / 药理）</option>
              <option value="case">医案书（病例集）</option>
            </select>
          </div>
          <div class="field">
            <label for="import-author">作者</label>
            <input id="import-author" v-model="form.author" class="input" placeholder="如：柯琴">
          </div>
          <div class="field">
            <label for="import-dynasty">朝代</label>
            <input id="import-dynasty" v-model="form.dynasty" class="input" placeholder="如：清">
          </div>
        </div>

        <div class="field">
          <label for="import-license">来源 / 版权声明 *</label>
          <textarea
            id="import-license"
            v-model="form.sourceLicense"
            class="input"
            rows="2"
            placeholder="如：公版古籍（作者已故逾百年）；或注明授权来源"
          ></textarea>
        </div>

        <div class="hr"></div>

        <h3 style="margin-bottom:12px">解析选项</h3>
        <div class="grid cols-2" style="gap:14px">
          <div class="field">
            <label for="import-visibility">可见性</label>
            <select id="import-visibility" v-model="form.visibility" class="input">
              <option value="private">仅自己可见</option>
              <option value="public">提交公共书架（需审核）</option>
            </select>
          </div>
        </div>
        <label class="muted" style="display:flex;gap:8px;align-items:center;font-size:13px;margin-bottom:8px">
          <input v-model="form.generateEmbedding" type="checkbox"> 生成向量（用于语义检索 / RAG 问答）
        </label>
        <label class="muted" style="display:flex;gap:8px;align-items:center;font-size:13px;margin-bottom:16px">
          <input v-model="form.extractHerbs" type="checkbox"> 抽取药味与剂量
        </label>

        <div v-if="error" style="margin-bottom:14px">
          <p class="muted" style="color:#A32D2D"><span class="badge err">提交失败</span> {{ error }}</p>
          <p class="muted" style="margin-top:4px">若为网络错误，请确认后端已启动（BFF :8090 / svc-catalog :8082）。</p>
        </div>

        <div style="display:flex;gap:10px;flex-wrap:wrap">
          <button class="btn primary" type="submit" :disabled="submitting">
            {{ submitting ? '提交中…' : '提交导入' }}
          </button>
          <RouterLink class="btn ghost" to="/shelf">取消</RouterLink>
        </div>
      </form>
    </div>

    <!-- 右侧须知 -->
    <aside style="display:grid;gap:16px;align-self:start">
      <div class="card">
        <h3 style="font-size:15px;margin-bottom:10px">导入须知</h3>
        <div class="timeline" style="margin-top:4px">
          <div class="ev">① 上传并填写信息</div>
          <div class="ev">② 系统自动解析章节 / 栏目</div>
          <div class="ev">③ 进入<b>治理审核</b>（质量校验）</div>
          <div class="ev">④ 通过后加入书架，可检索 / 练习</div>
        </div>
      </div>
      <div class="card">
        <h3 style="font-size:15px;margin-bottom:8px">版权提示</h3>
        <p class="muted" style="font-size:13px">
          古籍原文（作者已故久远）属公版可自由导入；现代教材、题库等受著作权保护，请确保拥有授权，或仅作个人学习使用（不公开）。
        </p>
      </div>
      <div class="card">
        <h3 style="font-size:15px;margin-bottom:8px">插拔式</h3>
        <p class="muted" style="font-size:13px">
          导入 = 注册语料 + 通用解析，无需改系统。详见计划文档 14 · 插拔式书籍扩展方案。
        </p>
      </div>
    </aside>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { getImportStatus, importBook, type ImportStatus } from '@/api/catalog'
import { toast } from '@/utils/toast'

interface ImportForm {
  title: string
  bookType: string
  author: string
  dynasty: string
  sourceLicense: string
  /** private = 仅自己可见；public = 提交公共书架（需审核） */
  visibility: string
  generateEmbedding: boolean
  extractHerbs: boolean
}

const steps = ['上传文件', '填写信息', '解析预览', '提交审核']

const form = reactive<ImportForm>({
  title: '',
  bookType: 'fz',
  author: '',
  dynasty: '',
  sourceLicense: '',
  visibility: 'private',
  generateEmbedding: true,
  extractHerbs: true
})

const submitting = ref(false)
const error = ref('')
const result = ref<ImportStatus | null>(null)
const statusLoading = ref(false)
const statusError = ref('')

const submitted = computed(() => result.value !== null)

function onDropzone() {
  toast('原型阶段仅登记元信息，文件解析由 ETL 完成')
}

async function onSubmit() {
  if (submitting.value) return

  const title = form.title.trim()
  const license = form.sourceLicense.trim()
  if (!title) {
    toast('请填写书名')
    error.value = '书名不能为空。'
    return
  }
  if (!license) {
    toast('请填写来源 / 版权声明')
    error.value = '来源 / 版权声明不能为空。'
    return
  }

  submitting.value = true
  error.value = ''
  statusError.value = ''
  try {
    result.value = await importBook({
      title,
      bookType: form.bookType,
      author: form.author.trim() || undefined,
      dynasty: form.dynasty.trim() || undefined,
      sourceLicense: license,
      visibility: form.visibility,
      generateEmbedding: form.generateEmbedding,
      extractHerbs: form.extractHerbs
    })
    toast('已提交，进入治理审核')
  } catch (e) {
    result.value = null
    error.value = e instanceof Error ? e.message : '提交失败，请稍后重试'
  } finally {
    submitting.value = false
  }
}

async function refreshStatus() {
  if (!result.value) return
  statusLoading.value = true
  statusError.value = ''
  try {
    result.value = await getImportStatus(result.value.importId)
    toast('导入状态已刷新')
  } catch (e) {
    statusError.value = e instanceof Error ? e.message : '查询失败'
  } finally {
    statusLoading.value = false
  }
}
</script>
