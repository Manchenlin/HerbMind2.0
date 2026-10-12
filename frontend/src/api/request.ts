import axios from 'axios'

/**
 * 统一请求封装。
 * - baseURL = /api（Vite proxy → 网关 :8080）
 * - 请求头带 Authorization: Bearer <token>
 * - 响应拦截：剥掉 R<T> 外壳，直接返回 data（前端只认 camelCase 字段）
 * - 401/403：清 token 跳 /login
 */
const request = axios.create({ baseURL: '/api', timeout: 10000 })

request.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

request.interceptors.response.use(
  (res) => {
    const body = res.data
    if (body && typeof body === 'object' && 'code' in body) {
      if (body.code === 0) return body.data
      throw new Error(body.msg || '请求失败')
    }
    return body
  },
  (err) => {
    const status = err.response?.status
    if (status === 401 || status === 403) {
      localStorage.removeItem('token')
      if (location.pathname !== '/login') location.href = '/login'
    }
    return Promise.reject(err)
  }
)

export default request
