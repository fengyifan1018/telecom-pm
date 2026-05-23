<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { ROLE_MAP } from '../utils/constants'
import { ElMessage } from 'element-plus'
import { getNotifications, getUnreadCount, markNotificationRead, markAllRead } from '../api/tasks'
import http from '../api/index'

const router = useRouter()
const auth = useAuthStore()

const unreadCount = ref(0)
const notifications = ref([])
const showNotifications = ref(false)
const showPwdDialog = ref(false)
const pwdForm = ref({ old_password: '', new_password: '', confirm_password: '' })
const pwdLoading = ref(false)
const isAdmin = computed(() => auth.user?.role === 'admin')
const can = (key) => auth.hasPermission(key)

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
    ElMessage.error(e.response?.data?.detail || '修改失败')
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
    <el-aside width="200px" style="background: #001529">
      <div style="padding: 16px; color: #fff; font-size: 16px; font-weight: bold; text-align: center">
        通信项目管理
      </div>
      <el-menu
        :default-active="$route.path"
        background-color="#001529"
        text-color="#ffffffa6"
        active-text-color="#fff"
        router
      >
        <el-menu-item index="/">
          <span>工作台</span>
        </el-menu-item>
        <el-menu-item index="/projects">
          <span>项目管理</span>
        </el-menu-item>
        <el-menu-item index="/kanban">
          <span>任务看板</span>
        </el-menu-item>
        <el-menu-item v-if="can('menu.reports')" index="/reports">
          <span>报表中心</span>
        </el-menu-item>
        <el-menu-item v-if="can('menu.templates')" index="/templates">
          <span>模板管理</span>
        </el-menu-item>
        <el-menu-item v-if="can('menu.customers')" index="/customers">
          <span>客户管理</span>
        </el-menu-item>
        <el-menu-item v-if="can('menu.users')" index="/users">
          <span>用户管理</span>
        </el-menu-item>
        <el-menu-item v-if="can('menu.groups')" index="/groups">
          <span>用户组管理</span>
        </el-menu-item>
        <el-menu-item v-if="can('menu.permissions')" index="/permissions">
          <span>权限管理</span>
        </el-menu-item>
        <el-menu-item v-if="isAdmin" index="/audit">
          <span>操作审计</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header style="display: flex; align-items: center; justify-content: flex-end; gap: 16px; border-bottom: 1px solid #eee">
        <el-badge :value="unreadCount" :hidden="!unreadCount" :max="99">
          <el-button circle @click="openNotifications" title="消息通知">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
              <path d="M12 22c1.1 0 2-.9 2-2h-4c0 1.1.9 2 2 2zm6-6v-5c0-3.07-1.63-5.64-4.5-6.32V4c0-.83-.67-1.5-1.5-1.5s-1.5.67-1.5 1.5v.68C7.64 5.36 6 7.92 6 11v5l-2 2v1h16v-1l-2-2z"/>
            </svg>
          </el-button>
        </el-badge>
        <el-dropdown @command="handleCommand">
          <span style="cursor: pointer; display: flex; align-items: center; gap: 8px">
            <el-avatar :size="32">{{ auth.user?.display_name?.[0] }}</el-avatar>
            <span>{{ auth.user?.display_name }}</span>
            <span style="color: #999; font-size: 12px">({{ ROLE_MAP[auth.user?.role] }})</span>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="password">修改密码</el-dropdown-item>
              <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </el-header>

      <el-main style="background: #f5f5f5">
        <router-view />
      </el-main>
    </el-container>

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
      <div
        v-for="n in notifications"
        :key="n.id"
        class="notification-item"
        :class="{ unread: !n.is_read }"
        @click="handleMarkRead(n)"
      >
        <div class="notification-title">{{ n.title }}</div>
        <div class="notification-time">{{ n.created_at?.slice(0, 16).replace('T', ' ') }}</div>
      </div>
    </el-drawer>
  </el-container>
</template>

<style scoped>
.notification-item {
  padding: 12px;
  border-bottom: 1px solid #f0f0f0;
  cursor: pointer;
  border-radius: 4px;
}
.notification-item:hover {
  background: #f5f7fa;
}
.notification-item.unread {
  background: #ecf5ff;
}
.notification-title {
  font-size: 14px;
  color: #303133;
  margin-bottom: 4px;
}
.notification-time {
  font-size: 12px;
  color: #909399;
}
</style>
