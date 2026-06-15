<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { getProject, initProject, updateProject, suspendProject, resumeProject, deleteProject } from '../api/projects'
import { listTasks, listUsers } from '../api/tasks'
import { STATUS_MAP, PRODUCT_TYPE_MAP, PHASE_MAP, PHASE_ORDER_BY_PRODUCT, PHASE_ORDER } from '../utils/constants'
import PhaseProgress from '../components/PhaseProgress.vue'
import TaskDrawer from '../components/TaskDrawer.vue'
import GanttChart from '../components/GanttChart.vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import * as XLSX from 'xlsx'
import EmptyState from '../components/EmptyState.vue'
import { listCRs, createCR, approveCR, rejectCR } from '../api/change_requests'
import { listDeliverables, uploadDeliverable, deleteDeliverable } from '../api/deliverables'
import http from '../api/index'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const isAdmin = computed(() => auth.user?.role === 'admin')
const isSales = computed(() => auth.user?.role === 'sales')
const project = ref(null)
const tasks = ref([])
const loading = ref(true)
const drawerVisible = ref(false)
const selectedTask = ref(null)
const activeTab = ref('list')
const showEdit = ref(false)
const editForm = ref({})
const changeRequests = ref([])
const showCRDialog = ref(false)
const crForm = ref({ title: '', reason: '', description: '' })
const crLoading = ref(false)
const showRejectDialog = ref(false)
const rejectingCR = ref(null)
const rejectReason = ref('')
const isPmOrAdmin = computed(() => ['pm', 'admin'].includes(auth.user?.role))
const deliverablesByPhase = ref({})
const deliverableUploadTitle = ref('')
const deliverableUploadPhase = ref('')
const deliverableUploadRef = ref(null)
const pmUsers = ref([])

const groupedTasks = computed(() => {
  const order = PHASE_ORDER_BY_PRODUCT[project.value?.product_type] || PHASE_ORDER
  return order.map((phase) => ({
    phase,
    name: PHASE_MAP[phase] || phase,
    tasks: tasks.value.filter((t) => t.phase === phase),
  })).filter((g) => g.tasks.length > 0)
})

async function fetchData() {
  loading.value = true
  try {
    const [pRes, tRes, crRes, dRes, uRes] = await Promise.all([
      getProject(route.params.id),
      listTasks({ project_id: route.params.id, page_size: 100 }),
      listCRs(route.params.id),
      listDeliverables(route.params.id),
      listUsers(),
    ])
    pmUsers.value = (uRes.data || []).filter(u => u.role === 'pm')
    project.value = pRes.data
    tasks.value = tRes.data.items
    changeRequests.value = crRes.data
    const byPhase = {}
    for (const d of dRes.data) {
      if (!byPhase[d.phase]) byPhase[d.phase] = []
      byPhase[d.phase].push(d)
    }
    deliverablesByPhase.value = byPhase
  } finally {
    loading.value = false
  }
}

onMounted(fetchData)

async function handleInit() {
  try {
    await initProject(project.value.id)
    ElMessage.success('项目立项成功，任务已生成')
    await fetchData()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '操作失败')
  }
}

function openTask(task) {
  selectedTask.value = task
  drawerVisible.value = true
}

function openEdit() {
  editForm.value = {
    name: project.value.name,
    planned_start: project.value.planned_start,
    planned_end: project.value.planned_end,
    description: project.value.description || '',
    ...(!isSales.value && {
      priority: project.value.priority,
      pm_id: project.value.pm_id,
    }),
  }
  showEdit.value = true
}

async function handleEditSave() {
  try {
    await updateProject(project.value.id, editForm.value)
    ElMessage.success('项目信息已更新')
    showEdit.value = false
    await fetchData()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '更新失败')
  }
}

async function handleCancel() {
  try {
    await ElMessageBox.confirm('确定要取消该项目吗？此操作不可恢复。', '取消项目', {
      type: 'warning',
      confirmButtonText: '确认取消',
      cancelButtonText: '返回',
    })
    await updateProject(project.value.id, { status: 'cancelled' })
    ElMessage.success('项目已取消')
    await fetchData()
  } catch {}
}

async function handleSuspend() {
  try {
    const { value } = await ElMessageBox.prompt('请输入暂停原因', '暂停项目', {
      confirmButtonText: '确认暂停',
      cancelButtonText: '取消',
      inputValidator: (v) => !!v || '请输入暂停原因',
    })
    await suspendProject(project.value.id, { reason_category: 'other', reason: value })
    ElMessage.success('项目已暂停')
    await fetchData()
  } catch (e) {
    if (e !== 'cancel' && e?.response) ElMessage.error(e.response?.data?.detail || '操作失败')
  }
}

async function handleResume() {
  try {
    await resumeProject(project.value.id)
    ElMessage.success('项目已恢复')
    await fetchData()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '操作失败')
  }
}

async function handleDelete() {
  try {
    await ElMessageBox.confirm(
      `确定要永久删除项目「${project.value.name}」吗？此操作不可恢复，所有任务数据将被清除。`,
      '删除项目',
      { type: 'error', confirmButtonText: '确认删除', cancelButtonText: '取消' }
    )
    await deleteProject(project.value.id)
    ElMessage.success('项目已删除')
    router.push('/projects')
  } catch (e) {
    if (e !== 'cancel' && e?.response) ElMessage.error(e.response?.data?.detail || '删除失败')
  }
}

function exportTasks() {
  const rows = tasks.value.map(t => ({
    '任务编号': t.task_no,
    '任务名称': t.title,
    '阶段': PHASE_MAP[t.phase] || t.phase,
    '状态': STATUS_MAP[t.status]?.label || t.status,
    '负责人': t.assignee_name || '',
    '计划开始': t.planned_start || '',
    '计划结束': t.planned_end || '',
    '优先级': t.priority,
  }))
  const ws = XLSX.utils.json_to_sheet(rows)
  const wb = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(wb, ws, '任务列表')
  XLSX.writeFile(wb, `${project.value.name}_任务列表.xlsx`)
}

async function onRefresh() {
  drawerVisible.value = false
  await fetchData()
}

async function handleUploadDeliverable(phase, file) {
  if (!file) return
  const title = window.prompt(`请输入文件标题 (${PHASE_MAP[phase] || phase})`, file.name.replace(/\.[^.]+$/, ''))
  if (!title) return
  const formData = new FormData()
  formData.append('phase', phase)
  formData.append('title', title)
  formData.append('file', file)
  try {
    await uploadDeliverable(project.value.id, formData)
    ElMessage.success('交付物已上传')
    const res = await listDeliverables(project.value.id)
    const byPhase = {}
    for (const d of res.data) {
      if (!byPhase[d.phase]) byPhase[d.phase] = []
      byPhase[d.phase].push(d)
    }
    deliverablesByPhase.value = byPhase
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '上传失败')
  }
}

async function handleDeleteDeliverable(d) {
  try {
    await ElMessageBox.confirm(`确定删除交付物「${d.title}」？`, '删除', { type: 'warning' })
    await deleteDeliverable(project.value.id, d.id)
    ElMessage.success('已删除')
    const res = await listDeliverables(project.value.id)
    const byPhase = {}
    for (const item of res.data) {
      if (!byPhase[item.phase]) byPhase[item.phase] = []
      byPhase[item.phase].push(item)
    }
    deliverablesByPhase.value = byPhase
  } catch (e) {
    if (e !== 'cancel' && e?.response) ElMessage.error(e.response?.data?.detail || '删除失败')
  }
}

async function handleDownloadDeliverable(d) {
  try {
    const res = await http.get(`/projects/${project.value.id}/deliverables/${d.id}/download`, { responseType: 'blob' })
    const url = URL.createObjectURL(new Blob([res.data]))
    const a = document.createElement('a')
    a.href = url
    a.download = d.title
    a.click()
    URL.revokeObjectURL(url)
  } catch {
    ElMessage.error('下载失败')
  }
}

async function handleCreateCR() {
  if (!crForm.value.title || !crForm.value.reason) {
    ElMessage.warning('标题和原因不能为空')
    return
  }
  crLoading.value = true
  try {
    await createCR(project.value.id, crForm.value)
    ElMessage.success('变更申请已提交')
    showCRDialog.value = false
    crForm.value = { title: '', reason: '', description: '' }
    const res = await listCRs(project.value.id)
    changeRequests.value = res.data
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '提交失败')
  } finally {
    crLoading.value = false
  }
}

async function handleApproveCR(cr) {
  try {
    await approveCR(project.value.id, cr.id)
    ElMessage.success('已批准')
    const res = await listCRs(project.value.id)
    changeRequests.value = res.data
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '操作失败')
  }
}

function openRejectCR(cr) {
  rejectingCR.value = cr
  rejectReason.value = ''
  showRejectDialog.value = true
}

async function handleRejectCR() {
  if (!rejectReason.value) {
    ElMessage.warning('请填写拒绝原因')
    return
  }
  try {
    await rejectCR(project.value.id, rejectingCR.value.id, { reject_reason: rejectReason.value })
    ElMessage.success('已拒绝')
    showRejectDialog.value = false
    const res = await listCRs(project.value.id)
    changeRequests.value = res.data
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '操作失败')
  }
}
</script>

<template>
  <div v-loading="loading">
    <template v-if="project">
      <el-breadcrumb separator="/" style="margin-bottom: 12px">
        <el-breadcrumb-item :to="{ path: '/projects' }">项目管理</el-breadcrumb-item>
        <el-breadcrumb-item>{{ project.project_no }}</el-breadcrumb-item>
      </el-breadcrumb>

      <!-- Header -->
      <el-card style="margin-bottom: 16px">
        <div style="display: flex; justify-content: space-between; align-items: flex-start">
          <div>
            <h3 style="margin: 0 0 8px">{{ project.name }}</h3>
            <el-space>
              <el-tag size="small">{{ project.project_no }}</el-tag>
              <el-tag :type="STATUS_MAP[project.status]?.type" size="small">{{ STATUS_MAP[project.status]?.label }}</el-tag>
              <el-tag type="info" size="small">{{ PRODUCT_TYPE_MAP[project.product_type] }}</el-tag>
            </el-space>
            <div style="margin-top: 8px; color: #909399; font-size: 13px; display: flex; gap: 24px; flex-wrap: wrap">
              <span v-if="project.customer_name">客户：{{ project.customer_name }}</span>
              <span v-if="project.sales_name">销售：{{ project.sales_name }}</span>
              <span v-if="project.pm_name">项目经理：{{ project.pm_name }}</span>
              <span>计划周期：{{ project.planned_start || '-' }} ~ {{ project.planned_end || '-' }}</span>
            </div>
          </div>
          <div style="display: flex; gap: 8px">
            <el-button v-if="project.status === 'draft' && !isSales" type="primary" @click="handleInit">
              立项（生成任务）
            </el-button>
            <el-button @click="openEdit">编辑</el-button>
            <el-button
              v-if="project.status === 'active'"
              type="warning"
              plain
              @click="handleSuspend"
            >暂停</el-button>
            <el-button
              v-if="project.status === 'suspended'"
              type="success"
              @click="handleResume"
            >恢复</el-button>
            <el-button
              v-if="project.status !== 'completed' && project.status !== 'cancelled'"
              type="danger"
              plain
              @click="handleCancel"
            >取消项目</el-button>
            <el-button
              v-if="isAdmin && project.status === 'cancelled'"
              type="danger"
              @click="handleDelete"
            >删除项目</el-button>
          </div>
        </div>
      </el-card>

      <!-- Project Details -->
      <el-card v-if="project.description" style="margin-bottom: 16px">
        <template #header>项目详情</template>
        <div style="white-space: pre-wrap; font-size: 14px; color: #303133; line-height: 1.7">{{ project.description }}</div>
      </el-card>

      <!-- Phase Progress -->
      <el-card v-if="tasks.length > 0" style="margin-bottom: 16px">
        <template #header>阶段进度</template>
        <PhaseProgress :tasks="tasks" :product-type="project.product_type" />
      </el-card>

      <!-- Task Views -->
      <el-card v-if="tasks.length > 0">
        <div style="display: flex; justify-content: flex-end; margin-bottom: 8px">
          <el-button size="small" @click="exportTasks">导出 Excel</el-button>
        </div>
        <el-tabs v-model="activeTab">
          <el-tab-pane label="任务列表" name="list">
            <div v-for="group in groupedTasks" :key="group.phase" style="margin-bottom: 20px">
              <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px">
                <h4 style="margin: 0; color: #303133">{{ group.name }}</h4>
                <el-upload
                  :auto-upload="false"
                  :show-file-list="false"
                  :on-change="(file) => handleUploadDeliverable(group.phase, file.raw)"
                  style="display: inline-block"
                >
                  <el-button size="small" text type="primary">+ 上传交付物</el-button>
                </el-upload>
              </div>
              <div v-if="deliverablesByPhase[group.phase]?.length" style="margin-bottom: 8px; padding: 6px 8px; background: #f0f9eb; border-radius: 4px; font-size: 12px">
                <span style="color: #67c23a; font-weight: bold">交付物：</span>
                <span v-for="d in deliverablesByPhase[group.phase]" :key="d.id" style="margin-left: 8px">
                  <a href="#" @click.prevent="handleDownloadDeliverable(d)" style="color: #409eff; text-decoration: none">{{ d.title }}</a>
                  <el-button size="small" type="danger" text @click.stop="handleDeleteDeliverable(d)" style="padding: 0 4px; margin-left: 2px">×</el-button>
                </span>
              </div>
              <el-table :data="group.tasks" size="small" @row-click="openTask" highlight-current-row style="cursor: pointer">
                <el-table-column prop="title" label="任务" min-width="200" />
                <el-table-column prop="status" label="状态" width="90">
                  <template #default="{ row }">
                    <el-tag :type="STATUS_MAP[row.status]?.type" size="small">{{ STATUS_MAP[row.status]?.label }}</el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="负责人" width="90">
                  <template #default="{ row }">
                    <span v-if="row.assignee_name">{{ row.assignee_name }}</span>
                    <span v-else style="color: #c0c4cc">-</span>
                  </template>
                </el-table-column>
                <el-table-column prop="planned_end" label="截止" width="110" />
              </el-table>
            </div>
          </el-tab-pane>
          <el-tab-pane label="甘特图" name="gantt">
            <GanttChart :tasks="tasks" />
          </el-tab-pane>
          <el-tab-pane label="变更申请" name="cr">
            <div style="display: flex; justify-content: flex-end; margin-bottom: 12px">
              <el-button size="small" type="primary" @click="showCRDialog = true">提交变更申请</el-button>
            </div>
            <EmptyState v-if="changeRequests.length === 0" text="暂无变更申请" />
            <el-table v-else :data="changeRequests" size="small">
              <el-table-column prop="cr_no" label="编号" width="160" />
              <el-table-column prop="title" label="标题" min-width="180" />
              <el-table-column prop="requester_name" label="申请人" width="100" />
              <el-table-column prop="status" label="状态" width="90">
                <template #default="{ row }">
                  <el-tag
                    :type="row.status === 'approved' ? 'success' : row.status === 'rejected' ? 'danger' : 'warning'"
                    size="small"
                  >{{ { pending: '待审批', approved: '已批准', rejected: '已拒绝' }[row.status] }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="created_at" label="提交时间" width="120">
                <template #default="{ row }">{{ row.created_at?.slice(0, 10) }}</template>
              </el-table-column>
              <el-table-column label="操作" width="140" v-if="isPmOrAdmin">
                <template #default="{ row }">
                  <template v-if="row.status === 'pending'">
                    <el-button size="small" type="success" @click="handleApproveCR(row)">批准</el-button>
                    <el-button size="small" type="danger" @click="openRejectCR(row)">拒绝</el-button>
                  </template>
                  <span v-else-if="row.reject_reason" style="color: #909399; font-size: 12px">{{ row.reject_reason }}</span>
                </template>
              </el-table-column>
            </el-table>
          </el-tab-pane>
        </el-tabs>
      </el-card>

      <EmptyState v-if="tasks.length === 0 && project.status === 'active'" text="暂无任务" />
    </template>

    <!-- Task Drawer -->
    <TaskDrawer v-model:visible="drawerVisible" :task="selectedTask" @refresh="onRefresh" />

    <!-- Edit Dialog -->
    <el-dialog v-model="showEdit" title="编辑项目" width="480px">
      <el-form label-width="80px">
        <el-form-item label="项目名称">
          <el-input v-model="editForm.name" />
        </el-form-item>
        <el-form-item v-if="!isSales" label="优先级">
          <el-select v-model="editForm.priority" style="width: 100%">
            <el-option :value="1" label="最高" />
            <el-option :value="2" label="高" />
            <el-option :value="3" label="中" />
            <el-option :value="4" label="低" />
          </el-select>
        </el-form-item>
        <el-form-item label="计划周期">
          <el-date-picker
            v-model="editForm.planned_start"
            type="date"
            placeholder="开始日期"
            value-format="YYYY-MM-DD"
            style="width: 48%"
          />
          <span style="margin: 0 4px">~</span>
          <el-date-picker
            v-model="editForm.planned_end"
            type="date"
            placeholder="结束日期"
            value-format="YYYY-MM-DD"
            style="width: 48%"
          />
        </el-form-item>
        <el-form-item v-if="!isSales" label="项目经理">
          <el-select v-model="editForm.pm_id" placeholder="选择项目经理" clearable filterable style="width: 100%">
            <el-option
              v-for="u in pmUsers"
              :key="u.id"
              :label="u.display_name"
              :value="u.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="项目详情">
          <el-input v-model="editForm.description" type="textarea" :rows="4" placeholder="项目背景、需求说明等" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showEdit = false">取消</el-button>
        <el-button type="primary" @click="handleEditSave">保存</el-button>
      </template>
    </el-dialog>

    <!-- CR Create Dialog -->
    <el-dialog v-model="showCRDialog" title="提交变更申请" width="480px">
      <el-form label-width="80px">
        <el-form-item label="标题">
          <el-input v-model="crForm.title" placeholder="简要描述变更内容" />
        </el-form-item>
        <el-form-item label="变更原因">
          <el-input v-model="crForm.reason" type="textarea" :rows="3" placeholder="说明为什么需要此变更" />
        </el-form-item>
        <el-form-item label="详细说明">
          <el-input v-model="crForm.description" type="textarea" :rows="2" placeholder="可选：方案详情、影响范围等" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCRDialog = false">取消</el-button>
        <el-button type="primary" :loading="crLoading" @click="handleCreateCR">提交</el-button>
      </template>
    </el-dialog>

    <!-- CR Reject Dialog -->
    <el-dialog v-model="showRejectDialog" title="拒绝变更申请" width="400px">
      <el-form label-width="80px">
        <el-form-item label="拒绝原因">
          <el-input v-model="rejectReason" type="textarea" :rows="3" placeholder="请说明拒绝原因" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showRejectDialog = false">取消</el-button>
        <el-button type="danger" @click="handleRejectCR">确认拒绝</el-button>
      </template>
    </el-dialog>
  </div>
</template>
