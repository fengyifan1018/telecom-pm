import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/Login.vue'),
    meta: { public: true },
  },
  {
    path: '/',
    component: () => import('../components/Layout.vue'),
    children: [
      { path: '', name: 'Workbench', component: () => import('../views/Workbench.vue'), meta: { title: '工作台' } },
      { path: 'projects', name: 'ProjectList', component: () => import('../views/ProjectList.vue'), meta: { title: '项目管理' } },
      { path: 'projects/:id', name: 'ProjectDetail', component: () => import('../views/ProjectDetail.vue'), meta: { title: '项目详情' } },
      { path: 'kanban', name: 'TaskKanban', component: () => import('../views/TaskKanban.vue'), meta: { title: '任务' } },
      { path: 'reports', name: 'Reports', component: () => import('../views/Reports.vue'), meta: { title: '报表中心' } },
      { path: 'templates', name: 'TemplateList', component: () => import('../views/TemplateList.vue'), meta: { title: '模板管理' } },
      { path: 'users', name: 'UserManage', component: () => import('../views/UserManage.vue'), meta: { title: '用户管理' } },
      { path: 'groups', name: 'GroupManage', component: () => import('../views/GroupManage.vue'), meta: { title: '用户组管理' } },
      { path: 'permissions', name: 'PermissionManage', component: () => import('../views/PermissionManage.vue'), meta: { title: '权限管理' } },
      { path: 'customers', name: 'CustomerManage', component: () => import('../views/CustomerManage.vue'), meta: { title: '客户管理' } },
      { path: 'audit', name: 'AuditLog', component: () => import('../views/AuditLog.vue'), meta: { title: '操作审计' } },
      { path: ':pathMatch(.*)*', name: 'NotFound', component: () => import('../views/NotFound.vue') },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (!to.meta.public && !auth.token) {
    return '/login'
  }
  // 硬刷新后 token 由 localStorage 恢复，但 user/permissions 丢失，需重新拉取
  if (auth.token && !auth.user) {
    try {
      await auth.fetchUser()
    } catch {
      auth.logout()
      return '/login'
    }
  }
})

export default router
