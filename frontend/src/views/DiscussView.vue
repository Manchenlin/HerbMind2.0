<template>
  <div class="crumb"><RouterLink to="/">首页</RouterLink> / 讨论区</div>
  <h1 class="serif" style="margin-bottom: 6px">讨论区</h1>
  <p class="muted" style="margin-bottom: 22px">
    方证辨疑、条文理解、练习心得。发话题和回复都会记在你自己的账号下。
  </p>

  <div class="grid" style="grid-template-columns: 1fr 330px">
    <section>
      <div v-if="loading" class="card"><p class="muted">正在加载话题…</p></div>
      <div v-else-if="error" class="card">
        <p class="muted" style="color: #a32d2d; margin-bottom: 12px">{{ error }}</p>
        <button class="btn ghost sm" @click="load">重试</button>
      </div>

      <div v-else-if="!data.topics.length" class="card center" style="padding: 48px 20px">
        <div style="font-size: 44px">💬</div>
        <p class="muted" style="margin: 12px 0 0">还没有人发话题，右边发第一个。</p>
      </div>

      <div v-else class="grid" style="gap: 12px">
        <div v-for="t in data.topics" :key="t.id" class="card">
          <div class="topic-head">
            <div style="min-width: 0">
              <b style="font-size: 15.5px">{{ t.title }}</b>
              <div class="muted" style="font-size: 12.5px">
                {{ t.author }} · {{ t.createdLabel }} · {{ t.floorCount }} 层
              </div>
            </div>
            <button class="btn ghost sm" @click="toggle(t.id)">
              {{ openId === t.id ? '收起' : '回复' }}
            </button>
          </div>

          <div style="margin-top: 10px">
            <p v-for="(f, i) in t.floors" :key="f.id" class="floor">
              <span class="muted">{{ i + 1 }} 楼 · {{ f.author }}：</span>
              {{ f.content }}
              <span v-if="f.isPinned" class="badge ok" style="margin-left: 6px">已被加精</span>
            </p>
            <p v-if="t.floorCount > t.floors.length" class="muted" style="font-size: 12.5px">
              还有 {{ t.floorCount - t.floors.length }} 层未展开（列表只带前 3 层）
            </p>
            <p v-if="!t.floors.length" class="muted" style="font-size: 13px">还没有人回复。</p>
          </div>

          <!-- 回复框 -->
          <div v-if="openId === t.id" style="margin-top: 12px">
            <textarea
              v-model="replyDraft"
              class="input"
              rows="3"
              placeholder="说说你的看法…"
            />
            <div style="display: flex; gap: 10px; margin-top: 10px; flex-wrap: wrap">
              <button class="btn primary sm" :disabled="replying" @click="reply(t.id)">
                {{ replying ? '发送中…' : '发布回复' }}
              </button>
              <button class="btn ghost sm" @click="cancelReply">取消</button>
            </div>
            <p v-if="replyError" class="muted" style="color: #a32d2d; margin-top: 8px">
              {{ replyError }}
            </p>
          </div>
        </div>
      </div>
    </section>

    <!-- 发话题 -->
    <aside class="card" style="align-self: start">
      <h3 style="margin-bottom: 12px">发个话题</h3>

      <div class="muted" style="margin-bottom: 6px">标题</div>
      <input v-model="form.title" class="input" placeholder="如：麻黄汤证为何不用桂枝汤？" />

      <div class="muted" style="margin: 12px 0 6px">内容</div>
      <textarea
        v-model="form.content"
        class="input"
        rows="5"
        placeholder="先把你的疑问或看法写清楚…"
      />

      <button
        class="btn primary"
        style="margin-top: 12px; width: 100%"
        :disabled="posting"
        @click="post"
      >
        {{ posting ? '发布中…' : '发布话题' }}
      </button>
      <p v-if="postError" class="muted" style="color: #a32d2d; margin-top: 10px">
        {{ postError }}
      </p>
      <p class="muted" style="font-size: 12px; margin-top: 12px">
        这里发的是公共话题；在方剂 / 医案页内的讨论会挂到具体内容上（接口已支持，等域1页面接入）。
      </p>
    </aside>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import {
  createTopic,
  getDiscuss,
  replyTopic,
  type DiscussList
} from '@/api/discuss'

const data = ref<DiscussList>({ topics: [], total: 0 })
const loading = ref(true)
const error = ref('')

const form = reactive({ title: '', content: '' })
const posting = ref(false)
const postError = ref('')

const openId = ref('')
const replyDraft = ref('')
const replying = ref(false)
const replyError = ref('')

async function load() {
  loading.value = true
  error.value = ''
  try {
    data.value = await getDiscuss()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

function toggle(id: string) {
  openId.value = openId.value === id ? '' : id
  replyDraft.value = ''
  replyError.value = ''
}

function cancelReply() {
  openId.value = ''
  replyDraft.value = ''
}

async function post() {
  if (posting.value) return
  if (!form.title.trim()) {
    postError.value = '标题不能为空'
    return
  }
  posting.value = true
  postError.value = ''
  try {
    // 公共话题：targetType=general，后端会把 target_id 记成 "-"
    data.value = await createTopic({
      targetType: 'general',
      targetId: '-',
      title: form.title.trim(),
      content: form.content.trim()
    })
    form.title = ''
    form.content = ''
  } catch (e) {
    postError.value = e instanceof Error ? e.message : '发布失败，请稍后重试'
  } finally {
    posting.value = false
  }
}

async function reply(topicId: string) {
  if (replying.value) return
  if (!replyDraft.value.trim()) {
    replyError.value = '回复不能为空'
    return
  }
  replying.value = true
  replyError.value = ''
  try {
    data.value = await replyTopic(topicId, replyDraft.value.trim())
    replyDraft.value = ''
    openId.value = ''
  } catch (e) {
    replyError.value = e instanceof Error ? e.message : '回复失败，请稍后重试'
  } finally {
    replying.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.topic-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}

.floor {
  font-size: 14px;
  line-height: 1.8;
  margin-bottom: 6px;
}

.floor:last-of-type {
  margin-bottom: 0;
}

@media (max-width: 900px) {
  .grid[style*='330px'] {
    grid-template-columns: 1fr !important;
  }
}
</style>
