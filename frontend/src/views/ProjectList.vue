<script setup>
import PageHeader from '../components/PageHeader.vue'
import EmptyState from '../components/EmptyState.vue'
import { formatDate } from '../utils/format'
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { listProjects, createProject, listCustomers, deleteProject } from '../api/projects'
import { listUsers, getOverview } from '../api/tasks'
import { STATUS_MAP, PRODUCT_TYPE_MAP, PRODUCT_TYPE_TAG, PRIORITY_MAP, ROLE_MAP } from '../utils/constants'
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

const overview = ref(null)
const stats = computed(() => {
  const p = overview.value?.projects || {}
  return [
    { key: 'active', label: '进行中', val: p.active, type: 'primary' },
    { key: 'draft', label: '草稿', val: p.draft, type: 'info' },
    { key: 'completed', label: '已完成', val: p.completed, type: 'success' },
    { key: '__overdue', label: '超期任务', val: overview.value?.overdue_tasks, type: 'danger' },
  ]
})
function onStatClick(s) {
  if (s.key === '__overdue') return
  filters.value.status = filters.value.status === s.key ? '' : s.key
}

const hasFilter = computed(() => !!(filters.value.search || filters.value.product_type || filters.value.status))
function resetFilters() {
  filters.value.search = ''
  filters.value.product_type = ''
  filters.value.status = ''
  filters.value.page = 1
  fetchProjects()
}

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
  const [cRes, uRes, oRes] = await Promise.all([listCustomers(), listUsers(), getOverview()])
  customers.value = cRes.data
  users.value = uRes.data
  overview.value = oRes.data
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
  getOverview().then(r => (overview.value = r.data))
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
    getOverview().then(r => (overview.value = r.data))
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

    <!-- 概览条 -->
    <div class="stat-strip">
      <div
        v-for="s in stats"
        :key="s.key"
        class="stat-card"
        :class="[`is-${s.type}`, { active: filters.status === s.key, clickable: s.key !== '__overdue' }]"
        @click="onStatClick(s)"
      >
        <div class="stat-accent" />
        <div class="stat-body">
          <div class="stat-val num">{{ s.val ?? '—' }}</div>
          <div class="stat-label">{{ s.label }}</div>
        </div>
      </div>
    </div>

    <el-card>
      <!-- 筛选工具条 -->
      <div class="toolbar">
        <div class="toolbar-filters">
          <el-input
            v-model="filters.search"
            placeholder="搜索项目名称/编号"
            clearable
            style="width: 220px"
            @input="handleSearch"
            @clear="fetchProjects"
          >
            <template #prefix><span class="search-ic">⌕</span></template>
          </el-input>
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
        <div class="toolbar-right">
          <span class="result-count">共 <b class="num">{{ total }}</b> 个项目</span>
          <el-button text :disabled="!hasFilter" @click="resetFilters">重置筛选</el-button>
        </div>
      </div>

      <el-skeleton v-if="loading" :rows="6" animated style="padding: 8px 0" />
      <el-table v-else stripe :data="projects" @row-click="goDetail" highlight-current-row class="project-table">
        <template #empty>
          <EmptyState text="暂无项目">
            <el-button type="primary" @click="showCreate = true">新建项目</el-button>
          </EmptyState>
        </template>
        <el-table-column prop="project_no" label="项目编号" width="160" />
        <el-table-column prop="name" label="项目名称" width="240" show-overflow-tooltip />
        <el-table-column prop="customer_name" label="客户" width="130" show-overflow-tooltip>
          <template #default="{ row }">{{ row.customer_name || '-' }}</template>
        </el-table-column>
        <el-table-column prop="product_type" label="产品线" width="100">
          <template #default="{ row }">
            <el-tag :type="PRODUCT_TYPE_TAG[row.product_type] || 'info'" size="small" effect="plain">
              {{ PRODUCT_TYPE_MAP[row.product_type] || row.product_type }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="priority" label="优先级" width="90">
          <template #default="{ row }">
            <el-tag v-if="PRIORITY_MAP[row.priority]" :type="PRIORITY_MAP[row.priority].type" size="small" effect="plain">
              {{ PRIORITY_MAP[row.priority].label }}
            </el-tag>
            <span v-else style="color: var(--el-text-color-placeholder)">-</span>
          </template>
        </el-table-column>
        <el-table-column label="计划周期" width="200">
          <template #default="{ row }">
            <span v-if="row.planned_start || row.planned_end" class="num" style="white-space: nowrap">
              {{ row.planned_start || '?' }} ~ {{ row.planned_end || '?' }}
            </span>
            <span v-else style="color: var(--el-text-color-placeholder)">-</span>
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
          <template #default="{ row }"><span class="num">{{ formatDate(row.created_at) }}</span></template>
        </el-table-column>
        <el-table-column v-if="isAdmin" label="操作" width="72" @click.stop>
          <template #default="{ row }">
            <el-button size="small" text type="danger" @click="handleDelete(row, $event)">删除</el-button>
          </template>
        </el-table-column>
        <el-table-column width="36" align="center">
          <template #default><span class="row-arrow">›</span></template>
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

<style scoped>
/* 概览条 */
.stat-strip {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}
.stat-card {
  display: flex;
  align-items: stretch;
  background: var(--el-bg-color, #fff);
  border: 1px solid var(--el-border-color);
  border-radius: var(--radius-md, 8px);
  overflow: hidden;
  transition: box-shadow 0.18s, border-color 0.18s, transform 0.18s;
}
.stat-card.clickable { cursor: pointer; }
.stat-card.clickable:hover {
  box-shadow: var(--shadow-card);
  transform: translateY(-1px);
}
.stat-accent {
  width: 4px;
  flex-shrink: 0;
  background: var(--el-color-info);
}
.stat-card.is-primary .stat-accent { background: var(--el-color-primary); }
.stat-card.is-success .stat-accent { background: var(--el-color-success); }
.stat-card.is-danger .stat-accent { background: var(--el-color-danger); }
.stat-card.is-info .stat-accent { background: var(--el-color-info); }
.stat-card.active {
  border-color: var(--el-color-primary);
  box-shadow: 0 0 0 2px var(--el-color-primary-light-8);
}
.stat-body { padding: 14px 16px; }
.stat-val {
  font-size: 28px;
  font-weight: 700;
  line-height: 1;
  color: var(--text-title);
}
.stat-label {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 8px;
}

/* 工具条 */
.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}
.toolbar-filters { display: flex; gap: 12px; flex-wrap: wrap; }
.toolbar-right {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 12px;
}
.result-count { font-size: 13px; color: var(--text-secondary); }
.result-count b { color: var(--el-color-primary); font-weight: 700; }
.search-ic { font-size: 15px; color: var(--text-secondary); }

/* 行箭头可供性 */
.row-arrow {
  font-size: 18px;
  line-height: 1;
  color: var(--el-text-color-placeholder);
  opacity: 0;
  transition: opacity 0.15s, transform 0.15s;
  display: inline-block;
}
.project-table :deep(.el-table__row:hover) .row-arrow {
  opacity: 1;
  transform: translateX(2px);
}
.project-table :deep(.el-table__row) { cursor: pointer; }
</style>
