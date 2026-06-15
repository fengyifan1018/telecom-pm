<script setup>
import PageHeader from '../components/PageHeader.vue'
import EmptyState from '../components/EmptyState.vue'
import { formatDate } from '../utils/format'
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { listProjects, createProject, listCustomers, deleteProject } from '../api/projects'
import { listUsers } from '../api/tasks'
import { STATUS_MAP, PRODUCT_TYPE_MAP, ROLE_MAP } from '../utils/constants'
import { useAuthStore } from '../stores/auth'
import { ElMessage, ElMessageBox } from 'element-plus'

const router = useRouter()
const auth = useAuthStore()
const isSales = computed(() => auth.user?.role === 'sales')
const isAdmin = computed(() => auth.user?.role === 'admin')
const projects = ref([])
const total = ref(0)
const loading = ref(false)
const filters = ref({ product_type: '', status: '', search: '', page: 1, page_size: 15 })

const emptyForm = () => ({
  name: '', customer_id: null, product_type: 'dia', priority: 3, pm_id: null,
  planned_start: '', planned_end: '', description: '',
})
const showCreate = ref(false)
const createForm = ref(emptyForm())
const customers = ref([])
const users = ref([])
let searchTimer = null

async function fetchProjects() {
  loading.value = true
  try {
    const params = { ...filters.value }
    if (!params.product_type) delete params.product_type
    if (!params.status) delete params.status
    if (!params.search) delete params.search
    const res = await listProjects(params)
    projects.value = res.data.items
    total.value = res.data.total
  } finally {
    loading.value = false
  }
}

function handleSearch(val) {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    filters.value.page = 1
    fetchProjects()
  }, 300)
}

onMounted(async () => {
  await fetchProjects()
  const [cRes, uRes] = await Promise.all([listCustomers(), listUsers()])
  customers.value = cRes.data
  users.value = uRes.data
})
watch(() => filters.value.product_type, fetchProjects)
watch(() => filters.value.status, fetchProjects)

function handlePageChange(page) {
  filters.value.page = page
  fetchProjects()
}

async function handleCreate() {
  if (!createForm.value.name) {
    ElMessage.warning('请输入项目名称')
    return
  }
  if (!createForm.value.customer_id) {
    ElMessage.warning('请选择客户')
    return
  }
  await createProject({ ...createForm.value })
  ElMessage.success('项目创建成功')
  showCreate.value = false
  createForm.value = emptyForm()
  fetchProjects()
}

function goDetail(row) {
  router.push(`/projects/${row.id}`)
}

async function handleDelete(row, e) {
  e.stopPropagation()
  try {
    await ElMessageBox.confirm(
      `确定要永久删除项目「${row.name}」吗？此操作不可恢复。`,
      '删除项目',
      { type: 'error', confirmButtonText: '确认删除', cancelButtonText: '取消' }
    )
    await deleteProject(row.id)
    ElMessage.success('项目已删除')
    fetchProjects()
  } catch (e) {
    // 取消无需提示，请求错误由全局拦截器统一处理
  }
}
</script>

<template>
  <div>
    <PageHeader title="项目管理">
      <el-button type="primary" @click="showCreate = true">新建项目</el-button>
    </PageHeader>

    <el-card>
      <div style="display: flex; gap: 12px; margin-bottom: 16px">
        <el-input
          v-model="filters.search"
          placeholder="搜索项目名称/编号"
          clearable
          style="width: 200px"
          @input="handleSearch"
          @clear="fetchProjects"
        />
        <el-select v-model="filters.product_type" placeholder="产品线" clearable style="width: 140px">
          <el-option v-for="(label, key) in PRODUCT_TYPE_MAP" :key="key" :label="label" :value="key" />
        </el-select>
        <el-select v-model="filters.status" placeholder="状态" clearable style="width: 120px">
          <el-option label="草稿" value="draft" />
          <el-option label="进行中" value="active" />
          <el-option label="已完成" value="completed" />
          <el-option label="已取消" value="cancelled" />
        </el-select>
      </div>

      <el-skeleton v-if="loading" :rows="6" animated style="padding: 8px 0" />
      <el-table v-else :data="projects" @row-click="goDetail" highlight-current-row style="cursor: pointer">
        <template #empty>
          <EmptyState text="暂无项目">
            <el-button type="primary" @click="showCreate = true">新建项目</el-button>
          </EmptyState>
        </template>
        <el-table-column prop="project_no" label="项目编号" width="160" />
        <el-table-column prop="name" label="项目名称" min-width="180" />
        <el-table-column prop="customer_name" label="客户" width="130">
          <template #default="{ row }">{{ row.customer_name || '-' }}</template>
        </el-table-column>
        <el-table-column prop="product_type" label="产品线" width="90">
          <template #default="{ row }">{{ PRODUCT_TYPE_MAP[row.product_type] || row.product_type }}</template>
        </el-table-column>
        <el-table-column label="计划周期" width="180">
          <template #default="{ row }">
            <span v-if="row.planned_start || row.planned_end">
              {{ row.planned_start || '?' }} ~ {{ row.planned_end || '?' }}
            </span>
            <span v-else style="color: #c0c4cc">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="STATUS_MAP[row.status]?.type" size="small">{{ STATUS_MAP[row.status]?.label }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="pm_name" label="项目经理" width="90">
          <template #default="{ row }">{{ row.pm_name || '-' }}</template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="110">
          <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
        </el-table-column>
        <el-table-column v-if="isAdmin" label="操作" width="80" @click.stop>
          <template #default="{ row }">
            <el-button size="small" text type="danger" @click="handleDelete(row, $event)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-if="total > filters.page_size"
        style="margin-top: 16px; justify-content: flex-end"
        layout="total, prev, pager, next"
        :total="total"
        :page-size="filters.page_size"
        :current-page="filters.page"
        @current-change="handlePageChange"
      />
    </el-card>

    <el-dialog v-model="showCreate" title="新建项目" width="540px">
      <el-form label-width="90px">
        <el-form-item label="项目名称" required>
          <el-input v-model="createForm.name" placeholder="如: XX客户DIA接入" />
        </el-form-item>
        <el-form-item label="客户" required>
          <el-select
            v-model="createForm.customer_id"
            placeholder="请选择客户"
            clearable
            filterable
            style="width: 100%"
          >
            <el-option v-for="c in customers" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="产品线">
          <el-select v-model="createForm.product_type" style="width: 100%">
            <el-option v-for="(label, key) in PRODUCT_TYPE_MAP" :key="key" :label="label" :value="key" />
          </el-select>
        </el-form-item>
        <el-form-item label="计划周期">
          <div style="display: flex; align-items: center; gap: 8px; width: 100%">
            <el-date-picker
              v-model="createForm.planned_start"
              type="date"
              placeholder="开始日期"
              value-format="YYYY-MM-DD"
              style="flex: 1"
            />
            <span>~</span>
            <el-date-picker
              v-model="createForm.planned_end"
              type="date"
              placeholder="结束日期"
              value-format="YYYY-MM-DD"
              style="flex: 1"
            />
          </div>
        </el-form-item>
        <el-form-item v-if="!isSales" label="项目经理">
          <el-select v-model="createForm.pm_id" placeholder="选择项目经理" clearable filterable style="width: 100%">
            <el-option
              v-for="u in users.filter(u => u.role === 'pm')"
              :key="u.id"
              :label="u.display_name"
              :value="u.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item v-if="!isSales" label="优先级">
          <el-select v-model="createForm.priority" style="width: 100%">
            <el-option :value="1" label="最高" />
            <el-option :value="2" label="高" />
            <el-option :value="3" label="中" />
            <el-option :value="4" label="低" />
          </el-select>
        </el-form-item>
        <el-form-item label="项目详情">
          <el-input v-model="createForm.description" type="textarea" :rows="3" placeholder="项目背景、需求说明等（可选）" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreate = false">取消</el-button>
        <el-button type="primary" @click="handleCreate">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>
