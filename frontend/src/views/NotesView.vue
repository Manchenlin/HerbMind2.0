<template>
  <div class="crumb">
    <RouterLink to="/">首页</RouterLink> / <RouterLink to="/me">我的</RouterLink> / 我的笔记
  </div>
  <h1 class="serif" style="margin-bottom: 6px">我的笔记</h1>
  <p class="muted" style="margin-bottom: 22px">
    笔记挂在具体的内容对象上（方剂 / 医案 / 条文），点标签可以回到原文。
  </p>

  <div v-if="loading" class="card"><p class="muted">正在加载笔记…</p></div>
  <div v-else-if="error" class="card">
    <p class="muted" style="color: #a32d2d; margin-bottom: 12px">{{ error }}</p>
    <button class="btn ghost sm" @click="load">重试</button>
  </div>

  <template v-else>
    <div class="grid" style="grid-template-columns: 1fr 330px">
      <!-- 列表 -->
      <section>
        <div v-if="!data.items.length" class="card center" style="padding: 48px 20px">
          <div style="font-size: 44px">📝</div>
          <p class="muted" style="margin: 12px 0 0">
            还没有笔记。先在右边选一个收藏对象，写第一条。
          </p>
        </div>

        <div v-else class="grid" style="gap: 12px">
          <div v-for="n in data.items" :key="n.id" class="card">
            <div class="note-head">
              <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap">
                <RouterLink :to="n.link" class="chip primary" style="font-size: 11.5px">
                  @{{ n.targetTitle }}
                </RouterLink>
                <span class="chip" style="font-size: 11.5px">{{ n.targetLabel }}</span>
                <span class="muted" style="font-size: 12px">{{ n.createdLabel }}</span>
              </div>
              <button class="btn ghost sm" @click="remove(n.id)">删除</button>
            </div>
            <p style="margin-top: 10px; line-height: 1.8; white-space: pre-wrap">
              {{ n.content }}
            </p>
          </div>
        </div>
        <p v-if="actionError" class="muted" style="color: #a32d2d; margin-top: 12px">
          {{ actionError }}
        </p>
      </section>

      <!-- 新建 -->
      <aside class="card" style="align-self: start">
        <h3 style="margin-bottom: 12px">写一条笔记</h3>

        <template v-if="favorites.length">
          <div class="muted" style="margin-bottom: 6px">挂在哪个对象上</div>
          <select v-model="form.targetId" class="input" style="margin-bottom: 12px">
            <option v-for="f in favorites" :key="f.id" :value="`${f.targetType}|${f.targetId}`">
              [{{ f.targetLabel }}] {{ f.title }}
            </option>
          </select>
          <div class="muted" style="margin-bottom: 6px">内容</div>
          <textarea
            v-model="form.content"
            class="input"
            rows="5"
            placeholder="如：麻黄汤 vs 桂枝汤，关键在「有汗/无汗、脉缓/脉紧」"
          />
          <button
            class="btn primary"
            style="margin-top: 12px; width: 100%"
            :disabled="saving"
            @click="save"
          >
            {{ saving ? '保存中…' : '保存笔记' }}
          </button>
          <p v-if="saveError" class="muted" style="color: #a32d2d; margin-top: 10px">
            {{ saveError }}
          </p>
        </template>

        <template v-else>
          <p class="muted" style="font-size: 13px">
            笔记必须挂在一个具体对象上。你还没有收藏，
            先去<RouterLink to="/library" style="color: var(--primary)">典籍</RouterLink>
            或<RouterLink to="/train" style="color: var(--primary)">练习</RouterLink>
            里收藏一个方剂 / 条文，再回来写。
          </p>
        </template>
      </aside>
    </div>
  </template>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import {
  getFavorites,
  getNotes,
  removeNote,
  saveNote,
  type FavoriteItem,
  type NoteList
} from '@/api/me'

const data = ref<NoteList>({ items: [], total: 0 })
const favorites = ref<FavoriteItem[]>([])
const loading = ref(true)
const error = ref('')
const actionError = ref('')

const saving = ref(false)
const saveError = ref('')
const form = reactive({ targetId: '', content: '' })

async function load() {
  loading.value = true
  error.value = ''
  try {
    // 新建表单要从收藏里挑对象：没有收藏就没有可挂载点，所以一并取回来
    const [notes, favs] = await Promise.all([getNotes(), getFavorites()])
    data.value = notes
    favorites.value = favs.items
    if (favs.items.length && !form.targetId) {
      form.targetId = `${favs.items[0].targetType}|${favs.items[0].targetId}`
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

async function save() {
  if (saving.value) return
  const content = form.content.trim()
  if (!content) {
    saveError.value = '写点什么再保存'
    return
  }
  const [targetType, targetId] = form.targetId.split('|')
  if (!targetType || !targetId) {
    saveError.value = '请选择要挂载的对象'
    return
  }

  saving.value = true
  saveError.value = ''
  try {
    data.value = await saveNote({ targetType, targetId, content })
    form.content = ''
  } catch (e) {
    saveError.value = e instanceof Error ? e.message : '保存失败，请稍后重试'
  } finally {
    saving.value = false
  }
}

async function remove(id: number) {
  actionError.value = ''
  try {
    data.value = await removeNote(id)
  } catch (e) {
    actionError.value = e instanceof Error ? e.message : '删除失败，请稍后重试'
  }
}

onMounted(load)
</script>

<style scoped>
.note-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

@media (max-width: 900px) {
  .grid[style*='330px'] {
    grid-template-columns: 1fr !important;
  }
}
</style>
