<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { listUsers } from '../api/tasks'
import { ROLE_MAP } from '../utils/constants'
import { ElMessage } from 'element-plus'
import http from '../api/index'
import PageHeader from '../components/PageHeader.vue'
import EmptyState from '../components/EmptyState.vue'

const users = ref([])
const loading = ref(false)
const page = ref(1)
const pageSize = ref(10)
const pagedUsers = computed(() =>
  users.value.slice((page.value - 1) * pageSize.value, page.value * pageSize.value),
)
watch(() => users.value.length, (len) => {
  const max = Math.max(1, Math.ceil(len / pageSize.value))
  if (page.value > max) page.value = max
})
const showDialog = ref(false)
const dialogTitle = ref('新增用户')
const form = ref({ username: '', password: '', display_name: '', role: 'operations' })
const editingId = ref(null)
const submitLoading = ref(false)

const ROLES = [
  { value: 'admin', label: '管理员' },
  { value: 'pm', label: '项目经理' },
  { value: 'sales', label: '销售' },
  { value: 'operations', label: '运营' },
  { value: 'procurement', label: '采购' },
  { value: 'network_engineer', label: '网络工程师' },
  { value: 'field_engineer', label: '现场实施' },
]

async function fetchUsers() {
  loading.value = true
  try {
    const res = await http.get('/users')
    users.value = res.data
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editingId.value = null
  dialogTitle.value = '新增用户'
  form.value = { username: '', password: '', display_name: '', role: 'operations' }
  showDialog.value = true
}

function openEdit(user) {
  editingId.value = user.id
  dialogTitle.value = '编辑用户'
  form.value = { display_name: user.display_name, role: user.role }
  showDialog.value = true
}

async function handleSubmit() {
  submitLoading.value = true
  try {
    if (editingId.value) {
      await http.put(`/users/${editingId.value}`, {
        display_name: form.value.display_name,
        role: form.value.role,
      })
      ElMessage.success('更新成功')
    } else {
      if (!form.value.username || !form.value.password || !form.value.display_name) {
        ElMessage.error('请填写完整信息')
        return
      }
      await http.post('/users', form.value)
      ElMessage.success('创建成功')
    }
    showDialog.value = false
    await fetchUsers()
  } catch (e) {
    // 错误提示由全局拦截器统一处理
  } finally {
    submitLoading.value = false
  }
}

async function deleteUser(user) {
  try {
    await http.delete(`/users/${user.id}`)
    ElMessage.success('已删除')
    await fetchUsers()
  } catch (e) {
    // 错误提示由全局拦截器统一处理
  }
}

async function toggleActive(user) {
  try {
    await http.put(`/users/${user.id}`, { is_active: !user.is_active })
    user.is_active = !user.is_active
    ElMessage.success(user.is_active ? '已启用' : '已禁用')
  } catch (e) {
    // 错误提示由全局拦截器统一处理
  }
}

onMounted(fetchUsers)
</script>

<template>
  <div>
    <PageHeader title="用户管理">
      <el-button type="primary" @click="openCreate">新增用户</el-button>
    </PageHeader>

    <el-skeleton v-if="loading" :rows="6" animated style="padding: 8px 0" />
    <el-table v-else :data="pagedUsers" border stripe>
      <template #empty><EmptyState text="暂无用户" /></template>
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="username" label="用户名" width="120" />
      <el-table-column prop="display_name" label="显示名" width="150" />
      <el-table-column prop="role" label="角色" width="120">
        <template #default="{ row }">{{ ROLE_MAP[row.role] || row.role }}</template>
      </el-table-column>
      <el-table-column prop="is_active" label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'danger'" size="small">
            {{ row.is_active ? '启用' : '禁用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="200">
        <template #default="{ row }">
          <el-button size="small" text type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button size="small" text :type="row.is_active ? 'danger' : 'success'" @click="toggleActive(row)">
            {{ row.is_active ? '禁用' : '启用' }}
          </el-button>
          <el-popconfirm title="确认删除该用户？" @confirm="deleteUser(row)">
            <template #reference>
              <el-button size="small" text type="danger">删除</el-button>
            </template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      v-if="!loading && users.length > 0"
      style="margin-top: 16px; justify-content: flex-end"
      layout="total, prev, pager, next"
      :total="users.length"
      :page-size="pageSize"
      :current-page="page"
      @current-change="page = $event"
    />

    <el-dialog v-model="showDialog" :title="dialogTitle" width="450px">
      <el-form label-width="80px">
        <el-form-item v-if="!editingId" label="用户名">
          <el-input v-model="form.username" placeholder="登录用户名" />
        </el-form-item>
        <el-form-item v-if="!editingId" label="密码">
          <el-input v-model="form.password" type="password" placeholder="初始密码" show-password />
        </el-form-item>
        <el-form-item label="显示名">
          <el-input v-model="form.display_name" placeholder="显示名称" />
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="form.role" style="width: 100%">
            <el-option v-for="r in ROLES" :key="r.value" :label="r.label" :value="r.value" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitLoading" @click="handleSubmit">确认</el-button>
      </template>
    </el-dialog>
  </div>
</template>
