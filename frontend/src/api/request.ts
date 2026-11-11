import axios from 'axios'

/**
 * 统一请求封装。
 * - baseURL = /api（Vite proxy → 网关 :8080）
 * - 请求头带 Authorization: Bearer <token>
 * - 响应拦截：剥掉 R<T> 外壳，直接返回 data（前端只认 camelCase 字段）
 * - 401：清 token 跳 /login（403 是"已登录但没权限"，不清 token，交给页面显示 msg）
 * - 其它错误：优先用后端 R.msg（09 契约要求 HTTP 状态码正确，axios 会走 error 分支）
 */
const request = axios.create({ baseURL: '/api', timeout: 15000 })

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
    const status: number | undefined = err.response?.status
    const msg: string | undefined = err.response?.data?.msg
    // 401 才是"登录态失效"，必须清 token 跳登录。
    // 403 是"已登录但没权限"（治理后台、他人资源），清 token 等于把用户踢出登录、
    // 还丢掉当前页面上下文 —— 交给调用方把 msg 显示出来。
    if (status === 401) {
      localStorage.removeItem('token')
      if (location.pathname !== '/login') location.href = '/login'
    }
    // 状态码挂到 Error 上：只留 message 的话，调用方分不出 4000（参数错）/4040（实体不存在）
    // /5000（服务异常），`api/graph.ts` 的 `httpStatus` 就是靠这个字段做分支的。
    const wrapped = new Error(msg || err.message || '请求失败') as Error & { status?: number }
    if (typeof status === 'number') wrapped.status = status
    return Promise.reject(wrapped)
  }
)

export default request
