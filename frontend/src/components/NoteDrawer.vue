<template>
  <div class="overlay" :class="{ open }" @click="$emit('close')"></div>
  <aside class="drawer" :class="{ open }">
    <div style="padding:20px">
      <h3 style="margin-bottom:12px">{{ title }}</h3>
      <textarea
        v-model="text"
        class="input"
        rows="7"
        placeholder="记录你的理解…（收藏 / 笔记接口由域2 提供，当前仅本地暂存）"
      ></textarea>
      <div style="margin-top:12px;display:flex;gap:10px">
        <button class="btn primary sm" @click="save">保存</button>
        <button class="btn ghost sm" @click="$emit('close')">取消</button>
      </div>
      <p class="muted" style="margin-top:12px;font-size:12.5px">
        登录后写入 <span class="mono">/api/biz/user/note</span>（域2 待接入）。
      </p>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { toast } from '@/utils/toast'

const props = defineProps<{ open: boolean; title: string; storageKey?: string }>()
const emit = defineEmits<{ (e: 'close'): void }>()

const text = ref('')

watch(
  () => props.open,
  (v) => {
    if (v && props.storageKey) {
      text.value = localStorage.getItem(props.storageKey) ?? ''
    }
  }
)

function save() {
  if (props.storageKey) localStorage.setItem(props.storageKey, text.value)
  toast('已保存笔记')
  emit('close')
}
</script>
