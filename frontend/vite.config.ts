import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 开发期：/api → 网关 :8080（网关再把 /api/biz/** 转给 BFF :8090）
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8080',
        changeOrigin: true
      }
    }
  }
})
