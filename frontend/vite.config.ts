import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 开发期：/api → 网关 :8080（网关再把 /api/biz/** 转给 BFF :8090）
export default defineConfig({
  plugins: [vue()],
  resolve: {
    // @ 别名必须在这里配（tsconfig 的 paths 只影响类型检查，不影响打包）
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
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
