<template>
  <div style="max-width:360px;margin:60px auto">
    <h2 style="text-align:center">登录 HerbMind</h2>
    <el-form @submit.prevent="onLogin">
      <el-form-item>
        <el-input v-model="username" placeholder="用户名" />
      </el-form-item>
      <el-form-item>
        <el-input v-model="password" type="password" placeholder="密码" show-password />
      </el-form-item>
      <el-button type="primary" style="width:100%" :loading="loading" @click="onLogin">登录</el-button>
      <p style="color:#9a9a97;font-size:12px;text-align:center;margin-top:12px">
        阶段 0 后接入 POST /api/biz/user/login
      </p>
    </el-form>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'

const username = ref('')
const password = ref('')
const loading = ref(false)
const router = useRouter()

// TODO(域2)：调用 POST /api/biz/user/login，存 token 后跳转
async function onLogin() {
  loading.value = true
  try {
    localStorage.setItem('token', 'demo-token')
    router.push('/library')
  } finally {
    loading.value = false
  }
}
</script>
