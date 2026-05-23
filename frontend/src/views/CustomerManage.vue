<script setup>
import { ref, onMounted, computed } from 'vue'
import { listCustomers, createCustomer, updateCustomer, deleteCustomer } from '../api/projects'
import { useAuthStore } from '../stores/auth'
import { ElMessage, ElMessageBox } from 'element-plus'

const auth = useAuthStore()
const canEdit = computed(() => ['admin', 'pm', 'sales'].includes(auth.user?.role))
const canDelete = computed(() => auth.user?.role === 'admin')

const customers = ref([])
const loading = ref(false)
const showDialog = ref(false)
const dialogTitle = ref('新增客户')
const form = ref({ name: '', contact_name: '', contact_phone: '' })
const editingId = ref(null)
const submitLoading = ref(false)
const search = ref('')

const filtered = computed(() => {
  const q = search.value.trim().toLowerCase()
  if (!q) return customers.value
  return customers.value.filter(c =>
    c.name.toLowerCase().includes(q) ||
    (c.contact_name || '').toLowerCase().includes(q) ||
    (c.contact_phone || '').includes(q)
  )
})

async function fetchCustomers() {
  loading.value = true
  try {
    const res = await listCustomers()
    customers.value = res.data
  } finally {
    loading.value = false
  }
}

onMounted(fetchCustomers)

function openCreate() {
  editingId.value = null
  dialogTitle.value = '新增客户'
  form.value = { name: '', contact_name: '', contact_phone: '' }
  showDialog.value = true
}

function openEdit(row) {
  editingId.value = row.id
  dialogTitle.value = '编辑客户'
  form.value = { name: row.name, contact_name: row.contact_name || '', contact_phone: row.contact_phone || '' }
  showDialog.value = true
}

async function handleSubmit() {
  if (!form.value.name.trim()) {
    ElMessage.error('请填写客户名称')
    return
  }
  submitLoading.value = true
  try {
    if (editingId.value) {
      await updateCustomer(editingId.value, form.value)
      ElMessage.success('更新成功')
    } else {
      await createCustomer(form.value)
      ElMessage.success('创建成功')
    }
    showDialog.value = false
    await fetchCustomers()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '操作失败')
  } finally {
    submitLoading.value = false
  }
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(
      `确定删除客户「${row.name}」吗？`,
      '确认删除',
      { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消' }
    )
    await deleteCustomer(row.id)
    ElMessage.success('已删除')
    await fetchCustomers()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.response?.data?.detail || '删除失败')
  }
}
</script>

<template>
  <div>
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px">
      <h2 style="margin: 0">客户管理</h2>
      <el-button v-if="canEdit" type="primary" @click="openCreate">新增客户</el-button>
    </div>

    <el-card>
      <div style="margin-bottom: 14px">
        <el-input
          v-model="search"
          placeholder="搜索客户名称 / 联系人 / 电话"
          clearable
          style="width: 260px"
        />
      </div>

      <el-table :data="filtered" v-loading="loading" border stripe>
        <el-table-column prop="name" label="客户名称" min-width="180" />
        <el-table-column prop="contact_name" label="联系人" width="120">
          <template #default="{ row }">{{ row.contact_name || '-' }}</template>
        </el-table-column>
        <el-table-column prop="contact_phone" label="联系电话" width="140">
          <template #default="{ row }">{{ row.contact_phone || '-' }}</template>
        </el-table-column>
        <el-table-column prop="project_count" label="关联项目" width="90" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="row.project_count ? 'primary' : 'info'">
              {{ row.project_count }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="120">
          <template #default="{ row }">{{ row.created_at?.slice(0, 10) }}</template>
        </el-table-column>
        <el-table-column v-if="canEdit" label="操作" width="130">
          <template #default="{ row }">
            <el-button size="small" text type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button
              v-if="canDelete"
              size="small"
              text
              type="danger"
              :disabled="row.project_count > 0"
              :title="row.project_count > 0 ? '该客户下存在项目，无法删除' : ''"
              @click="handleDelete(row)"
            >删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="showDialog" :title="dialogTitle" width="440px">
      <el-form label-width="80px">
        <el-form-item label="客户名称" required>
          <el-input v-model="form.name" placeholder="请输入客户名称" />
        </el-form-item>
        <el-form-item label="联系人">
          <el-input v-model="form.contact_name" placeholder="可选" />
        </el-form-item>
        <el-form-item label="联系电话">
          <el-input v-model="form.contact_phone" placeholder="可选" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitLoading" @click="handleSubmit">确认</el-button>
      </template>
    </el-dialog>
  </div>
</template>
