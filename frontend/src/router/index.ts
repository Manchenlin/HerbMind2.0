import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

/**
 * 完整页面清单（对齐 03 信息架构）。
 * 未实现的页面统一走 ComingSoonView —— 它会告诉你**负责人 + 要照哪个原型文件做**，
 * 这样三个人做出来的页面不会跑偏。
 */
const PAGES: Array<{ path: string; title: string; owner: string; proto: string }> = [
  // ---- 域1 内容域（读）----
  { path: '/', title: '首页', owner: '域1', proto: 'index.html' },
  { path: '/shelf', title: '书架 · 语料库', owner: '域1', proto: 'shelf.html' },
  { path: '/shelf/import', title: '导入语料', owner: '域1', proto: 'import.html' },
  { path: '/node/:id', title: '目录节点', owner: '域1', proto: 'library.html' },
  { path: '/formula/:id', title: '方剂详情', owner: '域1', proto: 'formula.html' },
  { path: '/case/:id', title: '案例详情', owner: '域1', proto: 'case.html' },
  { path: '/quote/:id', title: '条文详情', owner: '域1', proto: 'quote.html' },
  { path: '/search', title: '检索工作台', owner: '域1', proto: 'search.html' },
  { path: '/search/result', title: '结果分面', owner: '域1', proto: 'search-result.html' },
  { path: '/search/quote-index', title: '条文反向索引', owner: '域1', proto: 'search-result.html' },
  { path: '/research', title: '科研工作台', owner: '域1', proto: 'graph-map.html' },
  { path: '/research/export', title: '数据导出', owner: '域1', proto: 'graph-map.html' },
  // ---- 域2 成长域（练）----
  { path: '/train', title: '练习台', owner: '域2', proto: 'train.html' },
  { path: '/train/session/:id', title: '答题面板', owner: '域2', proto: 'answer.html' },
  { path: '/train/report/:id', title: '评分报告', owner: '域2', proto: 'report.html' },
  { path: '/train/blindbox', title: '案例盲盒', owner: '域2', proto: 'blindbox.html' },
  { path: '/train/recite', title: '背诵打卡', owner: '域2', proto: 'train.html' },
  { path: '/me', title: '我的 · 总览', owner: '域2', proto: 'me.html' },
  { path: '/me/profile', title: '学习档案', owner: '域2', proto: 'profile.html' },
  { path: '/me/favorites', title: '收藏夹', owner: '域2', proto: 'favorites.html' },
  { path: '/me/notes', title: '我的笔记', owner: '域2', proto: 'favorites.html' },
  { path: '/me/wrong', title: '错题本', owner: '域2', proto: 'profile.html' },
  { path: '/me/collection', title: '我的方证库', owner: '域2', proto: 'favorites.html' },
  { path: '/me/path', title: '学习路径', owner: '域2', proto: 'profile.html' },
  { path: '/discuss', title: '讨论区', owner: '域2', proto: 'case.html' }
  // 域3 智能域的 8 个页面已实现，见下方「域3（已实现）」段，此处不再列入占位
]

const routes: RouteRecordRaw[] = [
  // ---- 已实现 ----
  {
    path: '/library',
    name: 'library',
    component: () => import('@/views/LibraryView.vue'),
    meta: { title: '典籍浏览', owner: '域1', proto: 'library.html' }
  },
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/LoginView.vue'),
    meta: { title: '登录 / 注册', owner: '域2', proto: 'login.html' }
  },
  // ---- 域3 智能域（问）：8 页已实现，视觉照 graph / graph-map / ask / admin 四个原型 ----
  {
    path: '/graph',
    name: 'graph',
    component: () => import('@/views/GraphView.vue'),
    meta: { title: '图谱探索', owner: '域3', proto: 'graph.html' }
  },
  {
    path: '/graph/formula/:id',
    name: 'graph-formula',
    component: () => import('@/views/GraphFormulaView.vue'),
    meta: { title: '方心子图', owner: '域3', proto: 'graph.html' }
  },
  {
    path: '/graph/map',
    name: 'graph-map',
    component: () => import('@/views/GraphMapView.vue'),
    meta: { title: '相似度地图', owner: '域3', proto: 'graph-map.html' }
  },
  {
    path: '/ask',
    name: 'ask',
    component: () => import('@/views/AskView.vue'),
    meta: { title: '智能问答', owner: '域3', proto: 'ask.html' }
  },
  {
    path: '/ask/history',
    name: 'ask-history',
    component: () => import('@/views/AskHistoryView.vue'),
    meta: { title: '会话历史', owner: '域3', proto: 'ask.html' }
  },
  {
    path: '/admin',
    name: 'admin',
    component: () => import('@/views/AdminView.vue'),
    meta: { title: '治理后台', owner: '域3', proto: 'admin.html' }
  },
  {
    path: '/admin/review',
    name: 'admin-review',
    component: () => import('@/views/AdminReviewView.vue'),
    meta: { title: '复核工单', owner: '域3', proto: 'admin.html' }
  },
  {
    path: '/admin/issues',
    name: 'admin-issues',
    component: () => import('@/views/AdminIssuesView.vue'),
    meta: { title: 'OCR 疑点', owner: '域3', proto: 'admin.html' }
  },
  // ---- 待实现（占位，含负责人与原型指引）----
  ...PAGES.map<RouteRecordRaw>((p) => ({
    path: p.path,
    component: () => import('@/views/ComingSoonView.vue'),
    meta: { title: p.title, owner: p.owner, proto: p.proto, soon: true }
  })),
  { path: '/:pathMatch(.*)*', redirect: '/' }
]

const router = createRouter({ history: createWebHistory(), routes })

router.afterEach(() => {
  document.title = 'HerbMind 本草心智'
  document.body.classList.add('loaded')
})

export default router
