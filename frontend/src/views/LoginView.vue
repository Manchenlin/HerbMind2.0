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
          <button :class="{ active: panel === 'login' }" @click="panel = 'login'">登录</button>
          <button :class="{ active: panel === 'reg' }" @click="panel = 'reg'">注册</button>
        </div>

        <!-- 登录 -->
        <form v-if="panel === 'login'" @submit.prevent="doAuth('登录')">
          <div class="field">
            <label>用户名 / 邮箱</label>
            <input v-model="username" class="input" placeholder="请输入用户名" autocomplete="username" />
          </div>
          <div class="field">
            <label>密码</label>
            <input v-model="password" class="input" type="password" placeholder="请输入密码" autocomplete="current-password" />
          </div>
          <button class="btn primary" type="submit" style="width:100%;justify-content:center;margin-top:6px">登录</button>
          <div class="form-hint">阶段 0 后接入 POST /api/biz/user/login（域2）</div>
          <div class="center" style="margin-top:16px">
            <RouterLink class="btn ghost sm" to="/library">先逛逛，跳过登录 →</RouterLink>
          </div>
        </form>

        <!-- 注册 -->
        <form v-else @submit.prevent="doAuth('注册')">
          <div class="field"><label>用户名</label><input v-model="username" class="input" placeholder="设置用户名" /></div>
          <div class="field"><label>昵称</label><input class="input" placeholder="展示用昵称（可选）" /></div>
          <div class="field"><label>密码</label><input class="input" type="password" placeholder="设置密码" /></div>
          <div class="field"><label>确认密码</label><input class="input" type="password" placeholder="再次输入密码" /></div>
          <button class="btn primary" type="submit" style="width:100%;justify-content:center">注册并登录</button>
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

const panel = ref<'login' | 'reg'>('login')
const username = ref('')
const password = ref('')
const router = useRouter()

// TODO(域2)：调 POST /api/biz/user/login，写入 token 后跳转
function doAuth(what: string) {
  toast(`${what}成功，正在进入…`)
  localStorage.setItem('token', 'demo-token')
  setTimeout(() => router.push('/library'), 700)
}
</script>
