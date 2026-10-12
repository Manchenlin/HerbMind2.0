import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', redirect: '/library' },
  { path: '/library', name: 'library', component: () => import('@/views/LibraryView.vue') },
  { path: '/login', name: 'login', component: () => import('@/views/LoginView.vue') }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 401 由 request.ts 拦截后跳这里
router.beforeEach((to) => {
  const publicPages = ['/login']
  const token = localStorage.getItem('token')
  if (!token && !publicPages.includes(to.path)) {
    return '/login'
  }
  return true
})

export default router
