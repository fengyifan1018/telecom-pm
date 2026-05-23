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
      { path: '', name: 'Workbench', component: () => import('../views/Workbench.vue') },
      { path: 'projects', name: 'ProjectList', component: () => import('../views/ProjectList.vue') },
      { path: 'projects/:id', name: 'ProjectDetail', component: () => import('../views/ProjectDetail.vue') },
      { path: 'kanban', name: 'TaskKanban', component: () => import('../views/TaskKanban.vue') },
      { path: 'reports', name: 'Reports', component: () => import('../views/Reports.vue') },
      { path: 'templates', name: 'TemplateList', component: () => import('../views/TemplateList.vue') },
      { path: 'users', name: 'UserManage', component: () => import('../views/UserManage.vue') },
      { path: 'groups', name: 'GroupManage', component: () => import('../views/GroupManage.vue') },
      { path: 'permissions', name: 'PermissionManage', component: () => import('../views/PermissionManage.vue') },
      { path: 'customers', name: 'CustomerManage', component: () => import('../views/CustomerManage.vue') },
      { path: 'audit', name: 'AuditLog', component: () => import('../views/AuditLog.vue') },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (!to.meta.public && !auth.token) {
    return '/login'
  }
})

export default router
