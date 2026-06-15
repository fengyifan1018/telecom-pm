<script setup>
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { ROLE_MAP } from '../utils/constants'
import { ElMessage } from 'element-plus'
import {
  HomeFilled, Folder, Grid, Histogram, Document,
  OfficeBuilding, User, UserFilled, Lock, Tickets,
  Avatar, RefreshRight, Warning, AlarmClock, WarnTriangleFilled,
  CircleCheck, CircleClose, CircleCheckFilled, Promotion, ChatDotRound, Bell,
} from '@element-plus/icons-vue'
import { getNotifications, getUnreadCount, markNotificationRead, markAllRead } from '../api/tasks'
import http from '../api/index'
import BrandLogo from './BrandLogo.vue'

const router = useRouter()
const auth = useAuthStore()

const menus = [
  { path: '/', label: '工作台', icon: HomeFilled },
  { path: '/projects', label: '项目管理', icon: Folder },
  { path: '/kanban', label: '任务看板', icon: Grid },
  { path: '/reports', label: '报表中心', icon: Histogram, perm: 'menu.reports' },
  { path: '/templates', label: '模板管理', icon: Document, perm: 'menu.templates' },
  { path: '/customers', label: '客户管理', icon: OfficeBuilding, perm: 'menu.customers' },
  { path: '/users', label: '用户管理', icon: User, perm: 'menu.users' },
  { path: '/groups', label: '用户组管理', icon: UserFilled, perm: 'menu.groups' },
  { path: '/permissions', label: '权限管理', icon: Lock, perm: 'menu.permissions' },
  { path: '/audit', label: '操作审计', icon: Tickets, adminOnly: true },
]
const visibleMenus = computed(() =>
  menus.filter((m) => (m.adminOnly ? isAdmin.value : m.perm ? can(m.perm) : true)),
)

const unreadCount = ref(0)
const notifications = ref([])
const showNotifications = ref(false)
const showPwdDialog = ref(false)
const showMobileNav = ref(false)
const pwdForm = ref({ old_password: '', new_password: '', confirm_password: '' })
const pwdLoading = ref(false)
const isAdmin = computed(() => auth.user?.role === 'admin')
const can = (key) => auth.hasPermission(key)

const NOTIF_META = {
  task_assigned: { color: '#1890ff', icon: Avatar },
  task_status: { color: '#1890ff', icon: RefreshRight },
  overdue: { color: '#f56c6c', icon: Warning },
  due_soon: { color: '#e6a23c', icon: AlarmClock },
  escalation: { color: '#f56c6c', icon: WarnTriangleFilled },
  cr_submitted: { color: '#1890ff', icon: Document },
  cr_approved: { color: '#67c23a', icon: CircleCheck },
  cr_rejected: { color: '#f56c6c', icon: CircleClose },
  project_completed: { color: '#67c23a', icon: CircleCheckFilled },
  project_assigned: { color: '#1890ff', icon: Folder },
  project_initiated: { color: '#1890ff', icon: Promotion },
  comment_mention: { color: '#909399', icon: ChatDotRound },
}
function notifMeta(type) {
  return NOTIF_META[type] || { color: '#909399', icon: Bell }
}

const groupedNotifications = computed(() => {
  const todayStr = new Date().toISOString().slice(0, 10)
  const yestStr = new Date(Date.now() - 86400000).toISOString().slice(0, 10)
  const groups = { 今天: [], 昨天: [], 更早: [] }
  for (const n of notifications.value) {
    const d = n.created_at?.slice(0, 10)
    if (d === todayStr) groups['今天'].push(n)
    else if (d === yestStr) groups['昨天'].push(n)
    else groups['更早'].push(n)
  }
  return ['今天', '昨天', '更早']
    .filter((k) => groups[k].length)
    .map((k) => ({ label: k, items: groups[k] }))
})

const windowWidth = ref(window.innerWidth)
const onResize = () => { windowWidth.value = window.innerWidth }
onMounted(() => window.addEventListener('resize', onResize))
onUnmounted(() => window.removeEventListener('resize', onResize))
const isMobile = computed(() => windowWidth.value < 768)

async function fetchUnread() {
  try {
    const res = await getUnreadCount()
    unreadCount.value = res.data.count
  } catch {}
}

async function openNotifications() {
  showNotifications.value = true
  const res = await getNotifications()
  notifications.value = res.data
}

async function handleMarkRead(n) {
  if (!n.is_read) {
    await markNotificationRead(n.id)
    n.is_read = true
    unreadCount.value = Math.max(0, unreadCount.value - 1)
  }
  if (n.related_task_id && n.related_project_id) {
    showNotifications.value = false
    router.push(`/projects/${n.related_project_id}`)
  }
}

async function handleMarkAllRead() {
  await markAllRead()
  notifications.value.forEach(n => n.is_read = true)
  unreadCount.value = 0
}

function handleCommand(cmd) {
  if (cmd === 'logout') {
    auth.logout()
    router.push('/login')
  } else if (cmd === 'password') {
    pwdForm.value = { old_password: '', new_password: '', confirm_password: '' }
    showPwdDialog.value = true
  }
}

async function handleChangePwd() {
  if (pwdForm.value.new_password !== pwdForm.value.confirm_password) {
    ElMessage.error('两次密码不一致')
    return
  }
  if (pwdForm.value.new_password.length < 6) {
    ElMessage.error('密码长度不能少于6位')
    return
  }
  pwdLoading.value = true
  try {
    await http.put('/users/me/password', {
      old_password: pwdForm.value.old_password,
      new_password: pwdForm.value.new_password,
    })
    ElMessage.success('密码修改成功')
    showPwdDialog.value = false
  } catch (e) {
    // 错误提示由全局拦截器统一处理
  } finally {
    pwdLoading.value = false
  }
}

onMounted(() => {
  fetchUnread()
  setInterval(fetchUnread, 30000)
})
</script>

<template>
  <el-container style="height: 100vh">
    <!-- Desktop sidebar -->
    <el-aside v-if="!isMobile" width="200px" style="background: #001529">
      <div style="display: flex; justify-content: center; padding: 18px 16px">
        <BrandLogo :height="30" />
      </div>
      <el-menu
        :default-active="$route.path"
        background-color="#001529"
        text-color="#ffffffa6"
        active-text-color="#fff"
        router
      >
        <el-menu-item v-for="m in visibleMenus" :key="m.path" :index="m.path">
          <el-icon><component :is="m.icon" /></el-icon>
          <span>{{ m.label }}</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <!-- Header -->
      <el-header :style="isMobile ? 'display:flex;align-items:center;justify-content:space-between;padding:0 12px;border-bottom:1px solid #eee' : 'display:flex;align-items:center;justify-content:flex-end;gap:16px;border-bottom:1px solid #eee'">
        <!-- Mobile: hamburger -->
        <el-button v-if="isMobile" text @click="showMobileNav = true" style="font-size: 20px; padding: 4px">
          ☰
        </el-button>
        <span v-if="isMobile" style="font-weight: bold; font-size: 15px">通信项目管理</span>

        <div style="display: flex; align-items: center; gap: 12px">
          <el-badge :value="unreadCount" :hidden="!unreadCount" :max="99">
            <el-button circle @click="openNotifications" title="消息通知">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
                <path d="M12 22c1.1 0 2-.9 2-2h-4c0 1.1.9 2 2 2zm6-6v-5c0-3.07-1.63-5.64-4.5-6.32V4c0-.83-.67-1.5-1.5-1.5s-1.5.67-1.5 1.5v.68C7.64 5.36 6 7.92 6 11v5l-2 2v1h16v-1l-2-2z"/>
              </svg>
            </el-button>
          </el-badge>
          <el-dropdown @command="handleCommand">
            <span style="cursor: pointer; display: flex; align-items: center; gap: 6px">
              <el-avatar :size="32">{{ auth.user?.display_name?.[0] }}</el-avatar>
              <span v-if="!isMobile">{{ auth.user?.display_name }}</span>
              <span v-if="!isMobile" style="color: #999; font-size: 12px">({{ ROLE_MAP[auth.user?.role] }})</span>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="password">修改密码</el-dropdown-item>
                <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <el-main :style="isMobile ? 'background:var(--page-bg);padding:12px;padding-bottom:70px' : 'background:var(--page-bg)'">
        <router-view />
        <footer class="app-footer">通信项目管理系统 · v0.1.0 · © 2026</footer>
      </el-main>
    </el-container>

    <!-- Mobile slide-out nav -->
    <el-drawer v-if="isMobile" v-model="showMobileNav" direction="ltr" size="220px" :with-header="false">
      <div style="background:#001529;height:100%;overflow-y:auto">
        <div style="padding:20px 16px 12px">
          <BrandLogo :height="30" />
        </div>
        <el-menu
          :default-active="$route.path"
          background-color="#001529"
          text-color="#ffffffa6"
          active-text-color="#fff"
          router
          @select="showMobileNav = false"
        >
          <el-menu-item v-for="m in visibleMenus" :key="m.path" :index="m.path">
            <el-icon><component :is="m.icon" /></el-icon>
            <span>{{ m.label }}</span>
          </el-menu-item>
        </el-menu>
        <div style="padding:16px;border-top:1px solid #ffffff1a;margin-top:12px">
          <div style="color:#ffffffa6;font-size:13px">{{ auth.user?.display_name }}</div>
          <div style="color:#ffffff60;font-size:12px">{{ ROLE_MAP[auth.user?.role] }}</div>
        </div>
      </div>
    </el-drawer>

    <!-- Mobile bottom nav -->
    <div v-if="isMobile" class="mobile-bottom-nav">
      <router-link to="/" class="bottom-nav-item" :class="{ active: $route.path === '/' }">
        <svg viewBox="0 0 24 24" width="22" height="22" fill="currentColor"><path d="M10 20v-6h4v6h5v-8h3L12 3 2 12h3v8z"/></svg>
        <span>工作台</span>
      </router-link>
      <router-link to="/projects" class="bottom-nav-item" :class="{ active: $route.path.startsWith('/projects') }">
        <svg viewBox="0 0 24 24" width="22" height="22" fill="currentColor"><path d="M20 6h-2.18c.07-.44.18-.88.18-1a3 3 0 0 0-3-3c-1 0-1.96.54-2.5 1.35l-.5.67-.5-.68C10.96 2.54 10 2 9 2 7.34 2 6 3.34 6 5c0 .12.11.56.18 1H4c-1.1 0-2 .9-2 2v11c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2z"/></svg>
        <span>项目</span>
      </router-link>
      <router-link to="/kanban" class="bottom-nav-item" :class="{ active: $route.path === '/kanban' }">
        <svg viewBox="0 0 24 24" width="22" height="22" fill="currentColor"><path d="M4 6h2v12H4zm4 6h2v6H8zm4-3h2v9h-2zm4-5h2v14h-2z"/></svg>
        <span>看板</span>
      </router-link>
      <button class="bottom-nav-item" @click="showMobileNav = true">
        <svg viewBox="0 0 24 24" width="22" height="22" fill="currentColor"><path d="M3 18h18v-2H3v2zm0-5h18v-2H3v2zm0-7v2h18V6H3z"/></svg>
        <span>更多</span>
      </button>
    </div>

    <!-- Password Dialog -->
    <el-dialog v-model="showPwdDialog" title="修改密码" width="400px">
      <el-form label-width="80px">
        <el-form-item label="原密码">
          <el-input v-model="pwdForm.old_password" type="password" show-password />
        </el-form-item>
        <el-form-item label="新密码">
          <el-input v-model="pwdForm.new_password" type="password" show-password />
        </el-form-item>
        <el-form-item label="确认密码">
          <el-input v-model="pwdForm.confirm_password" type="password" show-password />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showPwdDialog = false">取消</el-button>
        <el-button type="primary" :loading="pwdLoading" @click="handleChangePwd">确认修改</el-button>
      </template>
    </el-dialog>

    <!-- Notification Drawer -->
    <el-drawer v-model="showNotifications" title="消息通知" size="380px">
      <div style="display: flex; justify-content: flex-end; margin-bottom: 12px">
        <el-button size="small" text type="primary" @click="handleMarkAllRead" :disabled="!unreadCount">
          全部已读
        </el-button>
      </div>
      <div v-if="notifications.length === 0" style="text-align: center; color: #909399; padding: 40px 0">
        暂无通知
      </div>
      <div v-for="g in groupedNotifications" :key="g.label" class="notif-group">
        <div class="notif-group__label">{{ g.label }}</div>
        <div
          v-for="n in g.items"
          :key="n.id"
          class="notification-item"
          :class="{ unread: !n.is_read }"
          @click="handleMarkRead(n)"
        >
          <el-icon
            class="notification-icon"
            :style="{ color: notifMeta(n.type).color, backgroundColor: notifMeta(n.type).color + '1a' }"
          >
            <component :is="notifMeta(n.type).icon" />
          </el-icon>
          <div class="notification-body">
            <div class="notification-title">{{ n.title }}</div>
            <div v-if="n.content" class="notification-content">{{ n.content }}</div>
            <div class="notification-time">{{ n.created_at?.slice(0, 16).replace('T', ' ') }}</div>
          </div>
        </div>
      </div>
    </el-drawer>
  </el-container>
</template>

<style scoped>
.app-footer {
  text-align: center;
  color: var(--text-secondary);
  font-size: 12px;
  padding: var(--sp-6) 0 var(--sp-2);
}
.mobile-bottom-nav {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  height: 56px;
  background: #fff;
  border-top: 1px solid #e8e8e8;
  display: flex;
  align-items: stretch;
  z-index: 1000;
  box-shadow: 0 -2px 8px rgba(0,0,0,.06);
}
.bottom-nav-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  font-size: 11px;
  color: #909399;
  text-decoration: none;
  border: none;
  background: none;
  cursor: pointer;
  padding: 0;
}
.bottom-nav-item.active, .bottom-nav-item.router-link-active {
  color: #409eff;
}
.bottom-nav-item span { line-height: 1; }

.notif-group {
  margin-bottom: var(--sp-2);
}
.notif-group__label {
  font-size: 12px;
  color: var(--text-secondary);
  font-weight: 600;
  padding: var(--sp-2) var(--sp-1) var(--sp-1);
}
.notification-item {
  display: flex;
  gap: var(--sp-3);
  padding: var(--sp-3);
  cursor: pointer;
  border-radius: var(--radius-md);
}
.notification-item:hover {
  background: #f5f7fa;
}
.notification-item.unread {
  background: var(--el-color-primary-light-9);
}
.notification-icon {
  flex-shrink: 0;
  width: 32px;
  height: 32px;
  border-radius: var(--radius-md);
  font-size: 18px;
}
.notification-body {
  flex: 1;
  min-width: 0;
}
.notification-title {
  font-size: 14px;
  color: var(--text-title);
  margin-bottom: 2px;
}
.notification-content {
  font-size: 12px;
  color: var(--text-regular);
  margin-bottom: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}
.notification-time {
  font-size: 12px;
  color: var(--text-secondary);
}
</style>
