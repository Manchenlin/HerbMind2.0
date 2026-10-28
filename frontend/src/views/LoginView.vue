<template>
  <div class="auth">
    <!-- 品牌侧 -->
    <aside class="auth-brand">
      <div class="logo-lg">H</div>
      <h1>一图见方证，<br />一问解经义，一练成明医。</h1>
      <p>可插拔的多语料中医知识平台 —— 以《中医经典方证案例研究》为首个语料，已接入《伤寒论》原文。</p>
      <div class="feats">
        <div>◆ 多维检索 · 语义问答（Agent 可溯源）</div>
        <div>◆ 先思后看 · AI 评分 · 错题本</div>
        <div>◆ 方-证-药-症 知识图谱 · 可插拔书架</div>
      </div>
    </aside>

    <!-- 表单侧 -->
    <main class="auth-form">
      <div class="inner">
        <div class="pill-tabs" style="margin-bottom:20px">
          <button :class="{ active: panel === 'login' }" @click="switchPanel('login')">登录</button>
          <button :class="{ active: panel === 'reg' }" @click="switchPanel('reg')">注册</button>
        </div>

        <!-- 错误提示（不引新 class，复用 form-hint + 内联色） -->
        <div v-if="error" class="form-hint" style="color:#c0392b;margin-bottom:12px">
          {{ error }}
        </div>

        <!-- 登录 -->
        <form v-if="panel === 'login'" @submit.prevent="doAuth('登录')">
          <div class="field">
            <label>用户名</label>
            <input v-model="username" class="input" placeholder="请输入用户名" autocomplete="username" />
          </div>
          <div class="field">
            <label>密码</label>
            <input v-model="password" class="input" type="password" placeholder="请输入密码" autocomplete="current-password" />
          </div>
          <button class="btn primary" type="submit" :disabled="loading" style="width:100%;justify-content:center;margin-top:6px">
            {{ loading ? '登录中…' : '登录' }}
          </button>
          <div class="form-hint">已接入 POST /api/biz/user/login（域2 svc-identity）</div>
          <div class="center" style="margin-top:16px">
            <span class="muted" style="font-size:13px">还没有账号？</span>
            <button class="btn ghost sm" type="button" style="margin-left:8px" @click="switchPanel('reg')">
              免费注册
            </button>
          </div>
        </form>

        <!-- 注册 -->
        <form v-else @submit.prevent="doAuth('注册')">
          <div class="field"><label>用户名</label><input v-model="username" class="input" placeholder="设置用户名" /></div>
          <div class="field"><label>昵称</label><input v-model="nickname" class="input" placeholder="展示用昵称（可选）" /></div>
          <div class="field"><label>密码</label><input v-model="password" class="input" type="password" placeholder="设置密码（至少 6 位）" /></div>
          <div class="field"><label>确认密码</label><input v-model="confirmPassword" class="input" type="password" placeholder="再次输入密码" /></div>
          <button class="btn primary" type="submit" :disabled="loading" style="width:100%;justify-content:center">
            {{ loading ? '注册中…' : '注册并登录' }}
          </button>
          <div class="form-hint">注册后即可以「学习者」身份开始练习</div>
        </form>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { toast } from '@/utils/toast'
import { login, register } from '@/api/user'

const panel = ref<'login' | 'reg'>('login')
const username = ref('')
const password = ref('')
const nickname = ref('')
const confirmPassword = ref('')
const loading = ref(false)
const error = ref('')
const router = useRouter()

function switchPanel(next: 'login' | 'reg') {
  panel.value = next
  error.value = ''
}

/** 登录 / 注册：成功后存 token 再跳转；失败只提示，不跳转。 */
async function doAuth(what: string) {
  error.value = ''

  if (!username.value.trim() || !password.value) {
    error.value = '请输入用户名和密码'
    return
  }
  if (panel.value === 'reg') {
    if (password.value.length < 6) {
      error.value = '密码至少 6 位'
      return
    }
    if (password.value !== confirmPassword.value) {
      error.value = '两次输入的密码不一致'
      return
    }
  }

  loading.value = true
  try {
    const res = panel.value === 'login'
      ? await login(username.value.trim(), password.value)
      : await register(username.value.trim(), password.value, nickname.value.trim() || undefined)

    // 只存 token，前端不解析 JWT（用户上下文由网关解析注入）
    localStorage.setItem('token', res.token)
    toast(`${what}成功，正在进入…`)
    router.push('/library')
  } catch (e: any) {
    // request 拦截器已把 code!=0 转成 Error(msg)，这里直接取
    const msg = e?.message || `${what}失败，请稍后重试`
    error.value = msg
    toast(msg)
  } finally {
    loading.value = false
  }
}
</script>
