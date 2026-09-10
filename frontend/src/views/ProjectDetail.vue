<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { getProject, initProject, submitInitiation, initApproval, updateProject, suspendProject, resumeProject, deleteProject, getProjectActivity, getProjectOpenEscalations } from '../api/projects'
import { listTasks, listUsers, assignTask } from '../api/tasks'
import { STATUS_MAP, PRODUCT_TYPE_MAP, PHASE_MAP, PHASE_ORDER_BY_PRODUCT, PHASE_ORDER, groupUsersByRole } from '../utils/constants'
import PhaseProgress from '../components/PhaseProgress.vue'
import { Tickets, CircleCheck, Clock, AlarmClock, ArrowDown, OfficeBuilding } from '@element-plus/icons-vue'
import TaskDrawer from '../components/TaskDrawer.vue'
import GanttChart from '../components/GanttChart.vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import EmptyState from '../components/EmptyState.vue'
import { formatDate, timeAgo, todayStr, dueColor } from '../utils/format'
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
const activeTab = ref('overview')
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
const members = ref([])
const memberGroups = computed(() => groupUsersByRole(members.value))
const activity = ref([])
const openEscalations = ref([])

// ── 概览驾驶舱：健康信号 ──
const today = todayStr()
const overdueTasks = computed(() =>
  tasks.value.filter(t => t.planned_end && t.planned_end < today && !['done', 'cancelled'].includes(t.status))
)
const doneCount = computed(() => tasks.value.filter(t => t.status === 'done').length)
const activeCount = computed(() => tasks.value.filter(t => ['active', 'review'].includes(t.status)).length)
const progressPct = computed(() => {
  const base = tasks.value.filter(t => t.is_required)
  const list = base.length ? base : tasks.value
  if (!list.length) return 0
  return Math.round(list.filter(t => t.status === 'done').length / list.length * 100)
})
// 验收阶段 = 模板倒数第二阶段；激活（含已完成）即"验收中"
const inAcceptance = computed(() => {
  const order = PHASE_ORDER_BY_PRODUCT[project.value?.product_type] || []
  const acc = order[order.length - 2]
  if (!acc) return false
  return tasks.value.some(t => t.phase === acc && ['active', 'review', 'done'].includes(t.status))
})
const health = computed(() => {
  if (project.value?.status === 'init_pending') return { label: '立项审核中', type: 'warning' }
  if (inAcceptance.value && project.value?.status === 'active') return { label: '验收中', type: 'primary' }
  if (openEscalations.value.length || overdueTasks.value.length) return { label: '有风险', type: 'danger' }
  if (project.value?.planned_end && project.value.planned_end < today && !['completed', 'cancelled'].includes(project.value.status)) {
    return { label: '已延期', type: 'warning' }
  }
  return { label: '正常', type: 'success' }
})
// 最近任务：未完成的按截止时间升序前 5 条
const recentTasks = computed(() =>
  tasks.value
    .filter(t => !['done', 'cancelled'].includes(t.status))
    .sort((x, y) => (x.planned_end || '9999') < (y.planned_end || '9999') ? -1 : 1)
    .slice(0, 5)
)
// 立项：管理层（有审核权限或非销售的 initiate 持有者）可直接立项；销售走立项审核
const canDirectInit = computed(() => {
  if (!project.value || project.value.status !== 'draft') return false
  if (auth.hasPermission('project.init_approve')) return true
  return !isSales.value && auth.hasPermission('project.initiate')
})
async function handleSubmitInitiation() {
  try {
    const res = await submitInitiation(project.value.id)
    project.value = res.data
    ElMessage.success('立项申请已提交，等待审核')
  } catch (e) {
    // 错误提示由全局拦截器统一处理
  }
}
async function handleInitApproval(action) {
  if (action === 'reject') {
    try {
      const { value } = await ElMessageBox.prompt('请填写驳回原因', '驳回立项申请', {
        confirmButtonText: '确认驳回', cancelButtonText: '取消',
        inputValidator: (v) => !!v || '请填写驳回原因',
      })
      const res = await initApproval(project.value.id, { action: 'reject', reason: value })
      project.value = res.data
      ElMessage.success('已驳回，项目退回待立项')
    } catch (e) {
      // 取消或接口错误由拦截器提示
    }
    return
  }
  try {
    const res = await initApproval(project.value.id, { action: 'approve' })
    ElMessage.success('审核通过，已完成立项')
    project.value = res.data
    await fetchData()
  } catch (e) {
    // 错误提示由全局拦截器统一处理
  }
}

function handleMoreCommand(cmd) {
  if (cmd === 'edit') openEdit()
  else if (cmd === 'suspend') handleSuspend()
  else if (cmd === 'resume') handleResume()
  else if (cmd === 'cancel') handleCancel()
  else if (cmd === 'delete') handleDelete()
}

const overviewStats = computed(() => [
  { label: '任务总数', value: tasks.value.length, color: 'var(--el-color-primary)', icon: Tickets },
  { label: '已完成', value: doneCount.value, color: 'var(--el-color-success)', icon: CircleCheck },
  { label: '进行中', value: activeCount.value, color: 'var(--el-color-warning)', icon: Clock },
  { label: '已延期', value: overdueTasks.value.length, color: 'var(--el-color-danger)', icon: AlarmClock },
])

// 项目阶段竖排看板：全部必要任务完成=已完成，任一进行=进行中
const phaseBoard = computed(() => {
  const order = PHASE_ORDER_BY_PRODUCT[project.value?.product_type] || []
  return order.map((key) => {
    const ts = tasks.value.filter(t => t.phase === key)
    const required = ts.filter(t => t.is_required)
    const base = required.length ? required : ts
    const done = ts.length > 0 && base.every(t => t.status === 'done')
    const active = !done && ts.some(t => ['active', 'review'].includes(t.status))
    const state = done ? 'done' : active ? 'active' : 'pending'
    const statusText = done ? '已完成' : active ? '进行中' : '未开始'
    const color = done ? 'var(--el-color-success)' : active ? 'var(--el-color-primary)' : 'var(--el-text-color-placeholder)'
    return { key, name: PHASE_MAP[key] || key, state, statusText, color }
  })
})

// 健康度评分：100 - 超期任务/升级各扣 10（封顶）/ 延期扣 15
const healthScore = computed(() => {
  let score = 100
  score -= Math.min(50, overdueTasks.value.length * 10)
  score -= Math.min(30, openEscalations.value.length * 10)
  if (project.value?.planned_end && project.value.planned_end < today && project.value.status === 'active') score -= 15
  return Math.max(0, score)
})
const healthScoreColor = computed(() =>
  healthScore.value >= 80 ? 'var(--el-color-success)' : healthScore.value >= 60 ? 'var(--el-color-warning)' : 'var(--el-color-danger)'
)
// 任务行内快捷指派（仅 PM/管理员）
const canAssign = computed(() => ['pm', 'admin'].includes(auth.user?.role))
async function quickAssign(row, userId) {
  if (!userId) return
  try {
    await assignTask(row.id, { assignee_id: userId })
    ElMessage.success('已指派')
    await fetchData()
  } catch { /* 错误由拦截器统一提示 */ }
}

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
    const [pRes, tRes, crRes, dRes, uRes, aRes, eRes] = await Promise.all([
      getProject(route.params.id),
      listTasks({ project_id: route.params.id, page_size: 100 }),
      listCRs(route.params.id),
      listDeliverables(route.params.id),
      listUsers(),
      getProjectActivity(route.params.id).catch(() => []),
      getProjectOpenEscalations(route.params.id).catch(() => []),
    ])
    pmUsers.value = (uRes.data || []).filter(u => u.role === 'pm')
    members.value = uRes.data || []
    activity.value = aRes.data
    openEscalations.value = eRes.data
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
    // 错误提示由全局拦截器统一处理
  }
}

function openTask(task) {
  selectedTask.value = task
  drawerVisible.value = true
}

// 抽屉内上一条/下一条导航
function onNavigateTask(id) {
  const t = tasks.value.find(t => t.id === id)
  if (t) selectedTask.value = t
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
    // 错误提示由全局拦截器统一处理
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
    // 取消无需提示，请求错误由全局拦截器统一处理
  }
}

async function handleResume() {
  try {
    await resumeProject(project.value.id)
    ElMessage.success('项目已恢复')
    await fetchData()
  } catch (e) {
    // 错误提示由全局拦截器统一处理
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
    // 取消无需提示，请求错误由全局拦截器统一处理
  }
}

async function exportTasks() {
  const XLSX = await import('xlsx')
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
    // 错误提示由全局拦截器统一处理
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
    // 取消无需提示，请求错误由全局拦截器统一处理
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
    // 错误提示由全局拦截器统一处理
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
    // 错误提示由全局拦截器统一处理
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
    // 错误提示由全局拦截器统一处理
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
    // 错误提示由全局拦截器统一处理
  }
}
</script>

<template>
  <div v-loading="loading">
    <template v-if="project">
      <!-- Header -->
      <el-card style="margin-bottom: 16px">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 24px">
          <div style="display: flex; gap: 16px; min-width: 0">
            <div class="project-icon">
              <el-icon :size="26" color="#fff"><OfficeBuilding /></el-icon>
            </div>
            <div style="min-width: 0">
              <h3 style="margin: 0 0 8px">{{ project.name }}</h3>
              <el-space>
                <el-tag size="small">{{ project.project_no }}</el-tag>
                <el-tag :type="STATUS_MAP[project.status]?.type" size="small">{{ STATUS_MAP[project.status]?.label }}</el-tag>
                <el-tag type="info" size="small">{{ PRODUCT_TYPE_MAP[project.product_type] }}</el-tag>
                <el-tag :type="health.type" size="small" effect="dark">● {{ health.label }}</el-tag>
              </el-space>
              <div style="margin-top: 8px; color: var(--el-text-color-secondary); font-size: 13px; display: flex; gap: 24px; flex-wrap: wrap">
                <span v-if="project.customer_name">客户：{{ project.customer_name }}</span>
                <span v-if="project.sales_name">销售：{{ project.sales_name }}</span>
                <span v-if="project.pm_name">项目经理：{{ project.pm_name }}</span>
                <span>计划周期：{{ project.planned_start || '-' }} ~ {{ project.planned_end || '-' }}</span>
              </div>
            </div>
          </div>
          <div style="display: flex; align-items: center; gap: 24px; flex-wrap: wrap">
            <div style="min-width: 200px">
              <div style="display: flex; justify-content: space-between; font-size: 12px; color: var(--el-text-color-secondary); margin-bottom: 4px">
                <span>项目进度</span><span class="num" style="font-weight: bold">{{ progressPct }}%</span>
              </div>
              <el-progress :percentage="progressPct" :stroke-width="10" :show-text="false" />
            </div>
            <div style="display: flex; gap: 8px; flex-wrap: wrap; align-items: center">
              <template v-if="project.status === 'draft'">
                <el-button v-if="canDirectInit" type="primary" @click="handleInit">
                  立项（生成任务）
                </el-button>
                <el-button v-else-if="auth.hasPermission('project.initiate')" type="primary" @click="handleSubmitInitiation">
                  提交立项审核
                </el-button>
              </template>
              <template v-if="project.status === 'init_pending' && auth.hasPermission('project.init_approve')">
                <el-button type="success" @click="handleInitApproval('approve')">通过并立项</el-button>
                <el-button type="warning" plain @click="handleInitReject">驳回</el-button>
              </template>
              <el-dropdown @command="handleMoreCommand">
                <el-button>
                  更多操作
                  <el-icon style="margin-left: 4px"><ArrowDown /></el-icon>
                </el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="edit">编辑项目</el-dropdown-item>
                    <el-dropdown-item v-if="project.status === 'active'" command="suspend">暂停项目</el-dropdown-item>
                    <el-dropdown-item v-if="project.status === 'suspended'" command="resume">恢复项目</el-dropdown-item>
                    <el-dropdown-item v-if="project.status !== 'completed' && project.status !== 'cancelled'" command="cancel" divided>取消项目</el-dropdown-item>
                    <el-dropdown-item v-if="isAdmin && project.status === 'cancelled'" command="delete" divided>删除项目</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>
          </div>
        </div>
      </el-card>

      <!-- Task Views -->
      <el-card v-if="tasks.length > 0">
        <div v-if="activeTab === 'list'" style="display: flex; justify-content: flex-end; margin-bottom: 8px">
          <el-button size="small" @click="exportTasks">导出 Excel</el-button>
        </div>
        <el-alert v-if="project.status === 'draft' && project.init_reject_reason" type="warning"
                :closable="false" show-icon style="margin-bottom: 16px"
                :title="`立项申请被驳回：${project.init_reject_reason}（可修改后重新提交）`" />

      <el-tabs v-model="activeTab">
        <el-tab-pane label="概览" name="overview">
      <!-- 概览统计 -->
      <el-row :gutter="12" style="margin-bottom: 16px">
        <el-col v-for="st in overviewStats" :key="st.label" :span="6">
          <div class="ov-stat">
            <div class="ov-stat__icon" :style="{ background: st.color }">
              <el-icon :size="20" color="#fff"><component :is="st.icon" /></el-icon>
            </div>
            <div>
              <div class="ov-stat__num num">{{ st.value }}</div>
              <div class="ov-stat__label">{{ st.label }}</div>
            </div>
          </div>
        </el-col>
      </el-row>

      <el-row :gutter="12" style="margin-bottom: 16px">
        <el-col :span="8">
          <el-card shadow="never" style="height: 100%">
            <div class="section-label">项目阶段</div>
            <div v-for="ph in phaseBoard" :key="ph.key" class="ov-phase-item">
              <span class="phase-dot" :class="'phase-dot--' + ph.state">
                <el-icon v-if="ph.state === 'done'" :size="12" color="#fff"><CircleCheck /></el-icon>
              </span>
              <span class="ov-phase-name">{{ ph.name }}</span>
              <span class="ov-phase-status" :style="{ color: ph.color }">{{ ph.statusText }}</span>
            </div>
          </el-card>
        </el-col>
        <el-col :span="8">
          <el-card shadow="never" style="height: 100%">
            <div class="section-label">项目风险 ({{ openEscalations.length + overdueTasks.length }})</div>
            <template v-if="openEscalations.length || overdueTasks.length">
              <div v-for="e in openEscalations" :key="e.id" class="ov-risk-item">
                <el-tag :type="e.severity === 'critical' || e.severity === 'high' ? 'danger' : 'warning'" size="small">
                  {{ { low: '低', medium: '中', high: '高', critical: '紧急' }[e.severity] }}
                </el-tag>
                <span class="ov-risk-title">{{ e.description }}</span>
                <span class="ov-risk-meta">{{ e.task_no }} · {{ timeAgo(e.created_at) }}</span>
              </div>
              <div v-for="t in overdueTasks" :key="'od' + t.id" class="ov-risk-item">
                <el-tag type="danger" size="small">超期</el-tag>
                <span class="ov-risk-title">{{ t.title }}</span>
                <span class="ov-risk-meta">{{ t.task_no }} · 截止 {{ t.planned_end }}</span>
              </div>
            </template>
            <div v-else style="color: var(--el-text-color-secondary); font-size: 13px">暂无风险项</div>
          </el-card>
        </el-col>
        <el-col :span="8">
          <el-card shadow="never" style="height: 100%">
            <div class="section-label">项目健康度</div>
            <div style="display: flex; justify-content: center; margin: 4px 0 10px">
              <el-progress type="circle" :percentage="healthScore" :width="104" :color="healthScoreColor"
                           :format="() => healthScore + ' 分'" />
            </div>
            <div class="ov-health-row"><span>进度</span><span class="num">{{ progressPct }}%</span></div>
            <div class="ov-health-row">
              <span>任务</span>
              <span :style="overdueTasks.length ? 'color: var(--el-color-danger)' : 'color: var(--el-color-success)'">
                {{ overdueTasks.length ? overdueTasks.length + ' 个延期' : '正常' }}
              </span>
            </div>
            <div class="ov-health-row">
              <span>风险</span>
              <span :style="openEscalations.length ? 'color: var(--el-color-danger)' : 'color: var(--el-color-success)'">
                {{ openEscalations.length ? openEscalations.length + ' 项升级' : '正常' }}
              </span>
            </div>
            <div class="ov-health-row">
              <span>计划</span>
              <span :style="project.planned_end && project.planned_end < today && project.status === 'active' ? 'color: var(--el-color-danger)' : 'color: var(--el-color-success)'">
                {{ project.planned_end && project.planned_end < today && project.status === 'active' ? '已延期' : '正常' }}
              </span>
            </div>
            <div class="ov-health-row"><span>验收</span><span>{{ inAcceptance ? '验收中' : '未开始' }}</span></div>
          </el-card>
        </el-col>
      </el-row>

      <el-row :gutter="12">
        <el-col :span="14">
          <el-card shadow="never" style="height: 100%">
            <div class="section-label">近期待办（按截止时间）</div>
            <el-table :data="recentTasks" @row-click="openTask" highlight-current-row style="cursor: pointer">
              <el-table-column prop="title" label="任务" min-width="200" show-overflow-tooltip />
              <el-table-column prop="assignee_name" label="负责人" width="100">
                <template #default="{ row }">{{ row.assignee_name || '—' }}</template>
              </el-table-column>
              <el-table-column label="截止" width="100">
                <template #default="{ row }">
                  <span class="num" :style="{ color: dueColor(row.planned_end) }">{{ row.planned_end || '—' }}</span>
                </template>
              </el-table-column>
              <el-table-column label="状态" width="86">
                <template #default="{ row }">
                  <el-tag :type="STATUS_MAP[row.status]?.type" size="small">{{ STATUS_MAP[row.status]?.label }}</el-tag>
                </template>
              </el-table-column>
            </el-table>
          </el-card>
        </el-col>
        <el-col :span="10">
          <el-card shadow="never" style="height: 100%">
            <div class="section-label">最近动态</div>
            <div v-if="activity.length === 0" style="color: var(--el-text-color-secondary); font-size: 13px">暂无动态</div>
            <div v-for="(a, i) in activity" :key="i" class="ov-activity-item">
              <span style="color: var(--el-color-primary)">{{ a.operator_name }}</span>
              <span style="font-size: 13px">{{ a.task_title }}（{{ a.from_status ? (STATUS_MAP[a.from_status]?.label || a.from_status) : '创建' }} → {{ STATUS_MAP[a.to_status]?.label || a.to_status }}）</span>
              <span class="ov-risk-meta" style="margin-left: auto">{{ timeAgo(a.created_at) }}</span>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <el-card v-if="project.description" shadow="never" style="margin-top: 16px">
        <div class="section-label">项目描述</div>
        <div class="task-description">{{ project.description }}</div>
      </el-card>
        </el-tab-pane>

          <el-tab-pane label="任务列表" name="list">
            <div v-for="group in groupedTasks" :key="group.phase" style="margin-bottom: 20px">
              <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px">
                <h4 style="margin: 0; font-size: 14px; font-weight: 600; color: var(--el-text-color-primary)">{{ group.name }}</h4>
                <el-upload
                  :auto-upload="false"
                  :show-file-list="false"
                  :on-change="(file) => handleUploadDeliverable(group.phase, file.raw)"
                  style="display: inline-block"
                >
                  <el-button size="small" text type="primary">+ 上传交付物</el-button>
                </el-upload>
              </div>
              <div v-if="deliverablesByPhase[group.phase]?.length" style="margin-bottom: 8px; padding: 6px 8px; background: var(--el-color-success-light-9); border-radius: 4px; font-size: 12px">
                <span style="color: var(--el-color-success); font-weight: bold">交付物：</span>
                <span v-for="d in deliverablesByPhase[group.phase]" :key="d.id" style="margin-left: 8px">
                  <a href="#" @click.prevent="handleDownloadDeliverable(d)" style="color: var(--el-color-primary); text-decoration: none">{{ d.title }}</a>
                  <el-button size="small" type="danger" text @click.stop="handleDeleteDeliverable(d)" style="padding: 0 4px; margin-left: 2px">×</el-button>
                </span>
              </div>
              <el-table stripe :data="group.tasks" size="small" @row-click="openTask" highlight-current-row style="cursor: pointer">
                <el-table-column prop="title" label="任务" min-width="200" show-overflow-tooltip/>
                <el-table-column prop="status" label="状态" width="90">
                  <template #default="{ row }">
                    <el-tag :type="STATUS_MAP[row.status]?.type" size="small">{{ STATUS_MAP[row.status]?.label }}</el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="负责人" width="130">
                  <template #default="{ row }">
                    <div v-if="canAssign" @click.stop>
                      <el-select :model-value="row.assignee_id" size="small" placeholder="点击指派"
                                 style="width: 110px" @change="(v) => quickAssign(row, v)">
                        <el-option-group v-for="g in memberGroups" :key="g.role" :label="g.label">
                          <el-option v-for="u in g.users" :key="u.id" :label="u.display_name" :value="u.id" />
                        </el-option-group>
                      </el-select>
                    </div>
                    <template v-else>
                      <span v-if="row.assignee_name">{{ row.assignee_name }}</span>
                      <span v-else style="color: var(--el-text-color-placeholder)">-</span>
                    </template>
                  </template>
                </el-table-column>
                <el-table-column prop="planned_end" label="截止" width="110" />
              </el-table>
            </div>
          </el-tab-pane>
          <el-tab-pane label="甘特图" name="gantt">
            <GanttChart :tasks="tasks" @refresh="onRefresh" />
          </el-tab-pane>
          <el-tab-pane label="变更申请" name="cr">
            <div style="display: flex; justify-content: flex-end; margin-bottom: 12px">
              <el-button size="small" type="primary" @click="showCRDialog = true">提交变更申请</el-button>
            </div>
            <EmptyState v-if="changeRequests.length === 0" text="暂无变更申请" />
            <el-table stripe v-else :data="changeRequests" size="small">
              <el-table-column prop="cr_no" label="编号" width="160" />
              <el-table-column prop="title" label="标题" min-width="180" show-overflow-tooltip/>
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
                <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
              </el-table-column>
              <el-table-column label="操作" width="140" v-if="isPmOrAdmin">
                <template #default="{ row }">
                  <template v-if="row.status === 'pending'">
                    <el-button size="small" type="success" @click="handleApproveCR(row)">批准</el-button>
                    <el-button size="small" type="danger" @click="openRejectCR(row)">拒绝</el-button>
                  </template>
                  <span v-else-if="row.reject_reason" style="color: var(--el-text-color-secondary); font-size: 12px">{{ row.reject_reason }}</span>
                </template>
              </el-table-column>
            </el-table>
          </el-tab-pane>
        </el-tabs>
      </el-card>

      <EmptyState v-if="tasks.length === 0 && project.status === 'active'" text="暂无任务" />
    </template>

    <!-- Task Drawer -->
    <TaskDrawer v-model:visible="drawerVisible" :task="selectedTask" :peer-ids="tasks.map(t => t.id)"
                @navigate="onNavigateTask" @refresh="onRefresh" />

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

<style scoped>
.ov-stat__icon {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.ov-stat__label { font-size: 13px; color: var(--el-text-color-secondary); }
.ov-phase-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 0;
  font-size: 13px;
}
.ov-phase-name { flex: 1; color: var(--el-text-color-primary); }
.ov-phase-status { font-size: 12px; }
.phase-dot {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  border: 2px solid var(--el-border-color);
  background: var(--el-bg-color);
}
.phase-dot--done { background: var(--el-color-success); border-color: var(--el-color-success); }
.phase-dot--active { border-color: var(--el-color-primary); }
.phase-dot--active::after {
  content: '';
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--el-color-primary);
}
.ov-health-row {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
  padding: 5px 0;
  border-bottom: 1px solid var(--el-border-color-lighter);
}
</style>

<style scoped>
.project-icon {
  width: 48px;
  height: 48px;
  border-radius: 10px;
  background: var(--el-color-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
</style>
