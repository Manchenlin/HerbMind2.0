<template>
  <div class="crumb">
    <RouterLink to="/">首页</RouterLink> / <RouterLink to="/me">我的</RouterLink> / 学习路径
  </div>
  <h1 class="serif" style="margin-bottom: 6px">学习路径</h1>
  <p class="muted" style="margin-bottom: 22px">
    一条从当前进度往下走的路线：练过的按时间排（看得见成长），没练的按同书优先推。
  </p>

  <div v-if="loading" class="card"><p class="muted">正在计算路径…</p></div>
  <div v-else-if="error" class="card">
    <p class="muted" style="color: #a32d2d; margin-bottom: 12px">{{ error }}</p>
    <button class="btn ghost sm" @click="load">重试</button>
  </div>

  <template v-else-if="p">
    <!-- 总进度 -->
    <div class="card" style="margin-bottom: 18px">
      <div style="display: flex; justify-content: space-between; align-items: baseline">
        <h3>整体进度</h3>
        <div class="muted">
          已练 <b style="color: var(--primary-deep)">{{ p.practiced }}</b> / {{ p.total }} 个可练单元
        </div>
      </div>
      <div class="bar" style="margin-top: 12px">
        <div class="fill" :style="{ width: `${p.percent}%` }" />
      </div>
      <p class="muted" style="font-size: 12.5px; margin-top: 8px">
        分母 = 全库真正挂了方药组成的单元数（当前 {{ p.total }} 个）。
        数据补齐后会一起变多，这个百分比就不是虚荣指标了。
      </p>
    </div>

    <div class="grid" style="grid-template-columns: 1fr 1fr">
      <!-- 已练 -->
      <section class="card">
        <h3 style="margin-bottom: 14px">已经走过（{{ p.done.length }}）</h3>
        <div v-if="!p.done.length" class="muted" style="font-size: 13.5px">
          还没练过。右边第一步就是起点。
        </div>
        <div v-else class="timeline">
          <div v-for="s in p.done" :key="s.nodeId" class="ev">
            <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap">
              <b>{{ s.title }}</b>
              <span v-if="s.score !== null" class="chip primary" style="font-size: 11px">
                {{ s.score }} 分
              </span>
            </div>
            <div class="muted" style="font-size: 12.5px">
              {{ s.bookTitle }} · {{ s.formulaCount }} 个方证 · {{ s.reason }}
            </div>
          </div>
        </div>
      </section>

      <!-- 待练 -->
      <section class="card">
        <h3 style="margin-bottom: 14px">接下来（{{ p.todo.length }} 步）</h3>
        <div v-if="!p.todo.length" class="muted" style="font-size: 13.5px">
          所有可练单元都练过了。等数据补齐后会有新单元。
        </div>
        <div v-else class="steps">
          <div v-for="s in p.todo" :key="s.nodeId" class="step" :class="{ doing: s.state === 'doing' }">
            <span class="num">{{ s.seq }}</span>
            <div style="flex: 1; min-width: 0">
              <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap">
                <b>{{ s.title }}</b>
                <span v-if="s.state === 'doing'" class="badge ok">下一站</span>
              </div>
              <div class="muted" style="font-size: 12.5px">{{ s.reason }}</div>
            </div>
            <button class="btn ghost sm" :disabled="starting === s.nodeId" @click="practice(s.nodeId)">
              {{ starting === s.nodeId ? '出题中…' : '去练' }}
            </button>
          </div>
        </div>
        <p v-if="actionError" class="muted" style="color: #a32d2d; margin-top: 10px">
          {{ actionError }}
        </p>
      </section>
    </div>
  </template>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getPath, type PathPlan } from '@/api/me'
import { startSession } from '@/api/train'

const router = useRouter()

const p = ref<PathPlan | null>(null)
const loading = ref(true)
const error = ref('')
const actionError = ref('')
const starting = ref('')

async function load() {
  loading.value = true
  error.value = ''
  try {
    p.value = await getPath()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

async function practice(nodeId: string) {
  if (starting.value) return
  starting.value = nodeId
  actionError.value = ''
  try {
    const q = await startSession(nodeId, '先思后看')
    sessionStorage.setItem('hm_question', JSON.stringify(q))
    router.push(`/train/session/${q.sessionId}`)
  } catch (e) {
    actionError.value = e instanceof Error ? e.message : '出题失败，请稍后重试'
  } finally {
    starting.value = ''
  }
}

onMounted(load)
</script>

<style scoped>
.bar {
  height: 10px;
  background: var(--surface-2);
  border-radius: 8px;
  overflow: hidden;
}

.bar .fill {
  height: 100%;
  background: linear-gradient(90deg, var(--primary), #4f8a8b);
  border-radius: 8px;
  transition: width 0.5s ease;
}

.steps {
  display: grid;
  gap: 10px;
}

.step {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--surface);
}

.step.doing {
  border-color: #cde6df;
  background: var(--primary-soft);
}

.step .num {
  width: 26px;
  height: 26px;
  border-radius: 8px;
  display: grid;
  place-items: center;
  font-size: 13px;
  font-weight: 700;
  background: var(--surface-2);
  color: var(--text-2);
  flex: none;
}

.step.doing .num {
  background: var(--primary);
  color: #fff;
}

@media (max-width: 900px) {
  .grid[style*='1fr 1fr'] {
    grid-template-columns: 1fr !important;
  }
}
</style>
