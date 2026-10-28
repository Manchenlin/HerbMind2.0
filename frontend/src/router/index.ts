import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

/**
 * 完整页面清单（对齐 03 信息架构）。
 * 域1（内容域）、域2（成长域）、域3（智能域）的页面均已接入真实组件，本数组当前为空。
 * 后续新增页面先在此登记「负责人 + 原型文件名」，占位页会据此提示该照哪个原型做，
 * 这样三个人做出来的页面不会跑偏。
 */
const PAGES: Array<{ path: string; title: string; owner: string; proto: string }> = [
  // 暂无待实现页面：三个域的页面均已实现，见下方 routes 中「已实现」各段
]

const routes: RouteRecordRaw[] = [
  // ================= 域1 内容域（已实现） =================
  {
    path: '/',
    name: 'home',
    component: () => import('@/views/HomeView.vue'),
    meta: { title: '首页', owner: '域1', proto: 'index.html' }
  },
  {
    path: '/shelf',
    name: 'shelf',
    component: () => import('@/views/ShelfView.vue'),
    meta: { title: '书架 · 语料库', owner: '域1', proto: 'shelf.html' }
  },
  {
    path: '/shelf/import',
    name: 'import',
    component: () => import('@/views/ImportView.vue'),
    meta: { title: '导入语料', owner: '域1', proto: 'import.html' }
  },
  {
    path: '/library',
    name: 'library',
    component: () => import('@/views/LibraryView.vue'),
    meta: { title: '典籍浏览', owner: '域1', proto: 'library.html' }
  },
  {
    path: '/node/:id',
    name: 'node',
    component: () => import('@/views/NodeView.vue'),
    meta: { title: '目录节点', owner: '域1', proto: 'library.html' }
  },
  {
    path: '/formula/:id',
    name: 'formula',
    component: () => import('@/views/FormulaView.vue'),
    meta: { title: '方剂详情', owner: '域1', proto: 'formula.html' }
  },
  {
    path: '/case/:id',
    name: 'case',
    component: () => import('@/views/CaseView.vue'),
    meta: { title: '案例详情', owner: '域1', proto: 'case.html' }
  },
  {
    path: '/quote/:id',
    name: 'quote',
    component: () => import('@/views/QuoteView.vue'),
    meta: { title: '条文详情', owner: '域1', proto: 'quote.html' }
  },
  {
    path: '/search',
    name: 'search',
    component: () => import('@/views/SearchView.vue'),
    meta: { title: '检索工作台', owner: '域1', proto: 'search.html' }
  },
  {
    path: '/search/result',
    name: 'search-result',
    component: () => import('@/views/SearchResultView.vue'),
    meta: { title: '结果分面', owner: '域1', proto: 'search-result.html' }
  },
  {
    path: '/search/quote-index',
    name: 'quote-index',
    component: () => import('@/views/QuoteIndexView.vue'),
    meta: { title: '条文反向索引', owner: '域1', proto: 'search-result.html' }
  },
  {
    path: '/research',
    name: 'research',
    component: () => import('@/views/ResearchView.vue'),
    meta: { title: '科研工作台', owner: '域1', proto: 'graph-map.html' }
  },
  {
    path: '/research/export',
    name: 'research-export',
    component: () => import('@/views/ResearchExportView.vue'),
    meta: { title: '数据导出', owner: '域1', proto: 'graph-map.html' }
  },
  // ================= 登录（域2） =================
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/LoginView.vue'),
    meta: { title: '登录 / 注册', owner: '域2', proto: 'login.html' }
  },
  {
    path: '/me',
    name: 'me',
    component: () => import('@/views/MeView.vue'),
    meta: { title: '我的 · 总览', owner: '域2', proto: 'me.html' }
  },
  {
    path: '/me/profile',
    name: 'me-profile',
    component: () => import('@/views/ProfileView.vue'),
    meta: { title: '学习档案', owner: '域2', proto: 'profile.html' }
  },
  {
    path: '/train',
    name: 'train',
    component: () => import('@/views/TrainView.vue'),
    meta: { title: '练习台', owner: '域2', proto: 'train.html' }
  },
  {
    path: '/train/session/:sessionId',
    name: 'train-session',
    component: () => import('@/views/AnswerView.vue'),
    meta: { title: '答题', owner: '域2', proto: 'answer.html' }
  },
  {
    path: '/train/report/:answerId',
    name: 'train-report',
    component: () => import('@/views/ReportView.vue'),
    meta: { title: '评分报告', owner: '域2', proto: 'report.html' }
  },
  {
    path: '/train/blindbox',
    name: 'train-blindbox',
    component: () => import('@/views/BlindboxView.vue'),
    meta: { title: '案例盲盒', owner: '域2', proto: 'blindbox.html' }
  },
  {
    path: '/train/recite',
    name: 'train-recite',
    component: () => import('@/views/ReciteView.vue'),
    meta: { title: '背诵打卡', owner: '域2', proto: 'train.html' }
  },
  {
    path: '/me/favorites',
    name: 'me-favorites',
    component: () => import('@/views/FavoritesView.vue'),
    meta: { title: '收藏夹', owner: '域2', proto: 'favorites.html' }
  },
  {
    path: '/me/notes',
    name: 'me-notes',
    component: () => import('@/views/NotesView.vue'),
    meta: { title: '我的笔记', owner: '域2', proto: 'favorites.html' }
  },
  {
    path: '/me/wrong',
    name: 'me-wrong',
    component: () => import('@/views/WrongBookView.vue'),
    meta: { title: '错题本', owner: '域2', proto: 'profile.html' }
  },
  {
    path: '/me/collection',
    name: 'me-collection',
    component: () => import('@/views/CollectionView.vue'),
    meta: { title: '我的方证库', owner: '域2', proto: 'favorites.html' }
  },
  {
    path: '/me/path',
    name: 'me-path',
    component: () => import('@/views/LearningPathView.vue'),
    meta: { title: '学习路径', owner: '域2', proto: 'profile.html' }
  },
  {
    path: '/discuss',
    name: 'discuss',
    component: () => import('@/views/DiscussView.vue'),
    meta: { title: '讨论区', owner: '域2', proto: 'case.html' }
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
