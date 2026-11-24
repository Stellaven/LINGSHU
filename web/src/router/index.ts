import { createRouter, createWebHistory } from 'vue-router'
import { isLoggedIn } from '@/stores/auth'

export const router = createRouter({
  history: createWebHistory(),
  scrollBehavior: () => ({ top: 0 }),
  routes: [
    {
      path: '/',
      name: 'home',
      // 首页：解析第一个团队并重定向到其详情页，无团队时显示引导空状态
      component: () => import('@/pages/HomePage.vue'),
    },
    {
      path: '/login',
      name: 'login',
      component: () => import('@/pages/LoginPage.vue'),
      // 公开页面：未登录可访问，且不渲染全局导航（见 App.vue）
      meta: { public: true, hideHeader: true },
    },
    {
      path: '/team/:teamId',
      component: () => import('@/pages/TeamDetailPage.vue'),
      children: [
        { path: '', redirect: (to) => `/team/${to.params.teamId}/projects` },
        {
          path: 'projects',
          name: 'team-projects',
          component: () => import('@/components/team/TeamProjectsPanel.vue'),
        },
        {
          path: 'members',
          name: 'team-members',
          component: () => import('@/components/team/TeamMembersPanel.vue'),
        },
        {
          path: 'settings',
          name: 'team-settings',
          component: () => import('@/components/team/TeamSettingsPanel.vue'),
        },
      ],
    },
    {
      path: '/team/:teamId/project/:projectId',
      component: () => import('@/pages/ProjectDetailPage.vue'),
      children: [
        { path: '', redirect: (to) => `/team/${to.params.teamId}/project/${to.params.projectId}/kbs` },
        {
          path: 'kbs',
          name: 'project-kbs',
          component: () => import('@/components/project/ProjectKnowledgePanel.vue'),
        },
        {
          path: 'members',
          name: 'project-members',
          component: () => import('@/components/project/ProjectMembersPanel.vue'),
        },
        {
          path: 'models',
          name: 'project-models',
          component: () => import('@/components/project/ProjectModelPanel.vue'),
        },
        {
          path: 'settings',
          name: 'project-settings',
          component: () => import('@/components/project/ProjectSettingsPanel.vue'),
        },
      ],
    },
    {
      path: '/knowledge/:kbId',
      name: 'kb-detail',
      component: () => import('@/pages/KnowledgeBaseDetail.vue'),
    },
    {
      path: '/knowledge/:kbId/files/:fileId',
      name: 'file-chunks',
      component: () => import('@/pages/FileChunks.vue'),
    },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

/**
 * 全局登录守卫：
 * - 未登录访问受保护页面 → 跳转登录页，并携带回跳地址
 * - 已登录访问登录页 → 回到首页（第一个团队详情）
 */
router.beforeEach((to) => {
  if (!to.meta.public && !isLoggedIn.value) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }
  if (to.name === 'login' && isLoggedIn.value) {
    return { path: '/' }
  }
})
