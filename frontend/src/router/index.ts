import { createRouter, createWebHashHistory } from 'vue-router'

// 使用 hash 路由（#/、#/test、#/result）：
// 兼容 GitHub Pages / 任意静态托管的 SPA 刷新与直达子路由
// （history 模式在静态托管上刷新 /test、/result 会 404）
const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    {
      path: '/',
      name: 'intro',
      component: () => import('@/views/IntroView.vue'),
    },
    {
      path: '/test',
      name: 'test',
      component: () => import('@/views/TestView.vue'),
    },
    {
      path: '/result',
      name: 'result',
      component: () => import('@/views/ResultView.vue'),
    },
    {
      path: '/:pathMatch(.*)*',
      name: 'not-found',
      component: () => import('@/views/NotFoundView.vue'),
    },
  ],
  scrollBehavior() {
    return { top: 0 }
  },
})

export default router
