<script setup>
import PageHeader from '../components/PageHeader.vue'
import EmptyState from '../components/EmptyState.vue'
import TaskListView from '../components/TaskListView.vue'
import { todayStr, dueTone } from '../utils/format'
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { listTasks, startTask, submitTask, approveTask, listUsers } from '../api/tasks'
import { listProjects } from '../api/projects'
import { STATUS_MAP, PHASE_MAP } from '../utils/constants'
import { ElMessage } from 'element-plus'

const route = useRoute()
const router = useRouter()
// query 取值：重复 key 取第一个
const q1 = (k) => {
  const v = route.query[k]
  return Array.isArray(v) ? v[0] : v
}
const tasks = ref([])
const projects = ref([])
const users = ref([])
const loading = ref(true)

// 视图模式（localStorage 持久化；URL 显式携带 ?view= 时优先）
const viewMode = ref(['kanban', 'list'].includes(q1('view')) ? q1('view') : (localStorage.getItem('task-view-mode') || 'kanban'))
watch(viewMode, (v) => localStorage.setItem('task-view-mode', v))

// 共享筛选（从 URL 初始化，变化时写回 URL）
const filterProject = ref(q1('project_id') ? Number(q1('project_id')) : '')
const filterPhase = ref(q1('phase') || '')
const filterAssignee = ref(q1('assignee_id') ? Number(q1('assignee_id')) : '')
const filterKeyword = ref(q1('keyword') || '')
const filterPriority = ref(q1('priority') ? Number(q1('priority')) : '')
const filterOverdue = ref(q1('overdue') === '1' || q1('overdue') === 'true')
const filterStatus = ref(q1('status') ? q1('status').split(',') : []) // 仅列表视图用

// 筛选状态同步到 URL（可分享/刷新不丢）
function syncQuery() {
  const q = {}
  if (filterProject.value) q.project_id = String(filterProject.value)
  if (filterPhase.value) q.phase = filterPhase.value
  if (filterAssignee.value) q.assignee_id = String(filterAssignee.value)
  if (filterKeyword.value) q.keyword = filterKeyword.value
  if (filterPriority.value) q.priority = String(filterPriority.value)
  if (filterOverdue.value) q.overdue = '1'
  if (filterStatus.value.length) q.status = filterStatus.value.join(',')
  router.replace({ query: q }).catch(() => {})
}

// 传给列表组件的筛选对象
const listFilters = computed(() => ({
  project_id: filterProject.value || undefined,
  phase: filterPhase.value || undefined,
  assignee_id: filterAssignee.value || undefined,
  keyword: filterKeyword.value || undefined,
  priority: filterPriority.value || undefined,
  overdue: filterOverdue.value || undefined,
  status: filterStatus.value,
}))

const draggingTask = ref(null)
const dragOverColumn = ref(null)

const columns = [
  { key: 'pending', label: '待分配', type: 'info' },
  { key: 'active', label: '进行中', type: 'primary' },
  { key: 'review', label: '待审核', type: 'warning' },
  { key: 'done', label: '已完成', type: 'success' },
  { key: '_exception', label: '异常', type: 'danger' },
]

const VALID_TRANSITIONS = {
  pending: { target: 'active', api: startTask },
  active: { target: 'review', api: (id) => submitTask(id) },
  review: { target: 'done', api: approveTask },
}

const PRIORITY_OPTIONS = [
  { value: 1, label: '最高' }, { value: 2, label: '高' }, { value: 3, label: '中' },
  { value: 4, label: '低' }, { value: 5, label: '最低' },
]
const STATUS_OPTIONS = ['pending', 'active', 'review', 'done', 'paused', 'blocked', 'cancelled']

const availablePhases = computed(() => {
  const phases = [...new Set(tasks.value.map(t => t.phase))]
  return phases.map(p => ({ key: p, label: PHASE_MAP[p] || p }))
})

// 看板取数：服务端筛选（不传 status，列本身即状态）；分页拉全量，超出上限提示
const KANBAN_MAX = 1000
async function fetchKanban() {
  loading.value = true
  try {
    const base = {}
    if (filterProject.value) base.project_id = filterProject.value
    if (filterPhase.value) base.phase = filterPhase.value
    if (filterAssignee.value) base.assignee_id = filterAssignee.value
    if (filterKeyword.value) base.keyword = filterKeyword.value
    if (filterPriority.value) base.priority = filterPriority.value
    if (filterOverdue.value) base.overdue = true
    const pageSize = 200
    const items = []
    let total = 0
    let page = 1
    do {
      const tRes = await listTasks({ ...base, page, page_size: pageSize })
      total = tRes.data.total
      items.push(...tRes.data.items)
      page += 1
    } while (items.length < total && items.length < KANBAN_MAX)
    if (items.length < total) {
      ElMessage.warning(`任务共 ${total} 条，看板仅加载前 ${items.length} 条，请用筛选缩小范围`)
    }
    tasks.value = items
  } finally {
    loading.value = false
  }
}

// 仅看板模式下，筛选变化时重新取数；同时把筛选同步到 URL
watch([filterProject, filterPhase, filterAssignee, filterKeyword, filterPriority, filterOverdue, filterStatus], () => {
  syncQuery()
  if (viewMode.value === 'kanban') fetchKanban()
})
watch(viewMode, (v) => { if (v === 'kanban') fetchKanban() })

const kanbanData = computed(() => columns.map((col) => ({
  ...col,
  tasks: col.key === '_exception'
    ? tasks.value.filter((t) => ['blocked', 'paused'].includes(t.status))
    : tasks.value.filter((t) => t.status === col.key),
})))

onMounted(async () => {
  const [pRes, uRes] = await Promise.all([listProjects({ page_size: 100 }), listUsers()])
  projects.value = pRes.data.items
  users.value = uRes.data
  if (viewMode.value === 'kanban') await fetchKanban()
  else loading.value = false
})

function goProject(task) { router.push(`/projects/${task.project_id}`) }

function clearAllFilters() {
  filterProject.value = ''
  filterPhase.value = ''
  filterAssignee.value = ''
  filterKeyword.value = ''
  filterPriority.value = ''
  filterOverdue.value = false
  filterStatus.value = []
}

function getProjectName(projectId) {
  const p = projects.value.find((p) => p.id === projectId)
  return p?.name?.slice(0, 10) || ''
}

function onDragStart(event, task) {
  if (['blocked', 'paused'].includes(task.status)) return
  draggingTask.value = task
  event.dataTransfer.effectAllowed = 'move'
}
function onDragEnd() { draggingTask.value = null; dragOverColumn.value = null }
function onDragOver(event, colKey) {
  if (colKey === '_exception') return
  const task = draggingTask.value
  if (!task) return
  const transition = VALID_TRANSITIONS[task.status]
  if (transition && transition.target === colKey) {
    event.preventDefault()
    event.dataTransfer.dropEffect = 'move'
    dragOverColumn.value = colKey
  }
}
function onDragLeave(colKey) { if (dragOverColumn.value === colKey) dragOverColumn.value = null }
async function onDrop(event, colKey) {
  event.preventDefault()
  dragOverColumn.value = null
  const task = draggingTask.value
  draggingTask.value = null
  if (!task) return
  const transition = VALID_TRANSITIONS[task.status]
  if (!transition || transition.target !== colKey) return
  try {
    await transition.api(task.id)
    task.status = colKey
    ElMessage.success('状态已更新')
  } catch (e) {
    await fetchKanban()
  }
}
</script>

<template>
  <div v-loading="loading">
    <PageHeader title="任务">
      <el-segmented v-model="viewMode" :options="[{ label: '看板', value: 'kanban' }, { label: '列表', value: 'list' }]" />
      <el-input v-model="filterKeyword" placeholder="搜索标题/编号" clearable style="width: 160px" />
      <el-select v-model="filterProject" placeholder="项目" clearable style="width: 150px" filterable>
        <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
      </el-select>
      <el-select v-model="filterPhase" placeholder="阶段" clearable style="width: 120px">
        <el-option v-for="p in availablePhases" :key="p.key" :label="p.label" :value="p.key" />
      </el-select>
      <el-select v-model="filterAssignee" placeholder="负责人" clearable filterable style="width: 130px">
        <el-option v-for="u in users" :key="u.id" :label="u.display_name" :value="u.id" />
      </el-select>
      <el-select v-model="filterPriority" placeholder="优先级" clearable style="width: 100px">
        <el-option v-for="o in PRIORITY_OPTIONS" :key="o.value" :label="o.label" :value="o.value" />
      </el-select>
      <el-select v-if="viewMode === 'list'" v-model="filterStatus" placeholder="状态" multiple collapse-tags clearable style="width: 160px">
        <el-option v-for="s in STATUS_OPTIONS" :key="s" :label="STATUS_MAP[s]?.label || s" :value="s" />
      </el-select>
      <el-checkbox v-model="filterOverdue">仅超期</el-checkbox>
    </PageHeader>

    <div v-if="viewMode === 'kanban'" class="kanban-board">
      <div
        v-for="col in kanbanData"
        :key="col.key"
        class="kanban-column"
        :class="{ 'drag-over': dragOverColumn === col.key }"
        @dragover="onDragOver($event, col.key)"
        @dragleave="onDragLeave(col.key)"
        @drop="onDrop($event, col.key)"
      >
        <div class="kanban-header">
          <el-tag :type="col.type" size="small">{{ col.label }}</el-tag>
          <span class="kanban-count">{{ col.tasks.length }}</span>
        </div>
        <div class="kanban-cards">
          <div
            v-for="task in col.tasks"
            :key="task.id"
            class="kanban-card"
            :class="{ dragging: draggingTask?.id === task.id, draggable: !!VALID_TRANSITIONS[task.status] }"
            :draggable="!!VALID_TRANSITIONS[task.status]"
            @dragstart="onDragStart($event, task)"
            @dragend="onDragEnd"
            @click="goProject(task)"
          >
            <div class="card-project">{{ getProjectName(task.project_id) }}</div>
            <div class="card-title">{{ task.title }}</div>
            <div class="card-meta">
              <span>{{ PHASE_MAP[task.phase] || task.phase }}</span>
              <span v-if="task.assignee_name" class="card-assignee">{{ task.assignee_name }}</span>
            </div>
            <el-tag v-if="col.key === '_exception'" :type="task.status === 'blocked' ? 'danger' : 'warning'" size="small" style="margin-top: 4px">{{ STATUS_MAP[task.status]?.label }}</el-tag>
            <div v-if="task.planned_end" class="card-due"
                 :class="{ 'is-overdue': task.planned_end < todayStr() && col.key !== 'done', 'is-soon': ['today','soon'].includes(dueTone(task.planned_end)) && col.key !== 'done' }">
              {{ task.planned_end }}<template v-if="dueTone(task.planned_end) === 'today'"> · 今天</template>
            </div>
            <div v-if="task.progress > 0 && task.status !== 'done'" class="card-progress">
              <div class="card-progress__fill" :style="{ width: task.progress + '%' }" />
            </div>
            <div v-if="VALID_TRANSITIONS[task.status]" class="drag-hint">拖拽→{{ STATUS_MAP[VALID_TRANSITIONS[task.status].target]?.label }}</div>
          </div>
          <EmptyState v-if="col.tasks.length === 0" text="" :size="28" />
        </div>
      </div>
    </div>
    <TaskListView v-else :filters="listFilters" @clear-filters="clearAllFilters" />
  </div>
</template>

<style scoped>
.kanban-board {
  display: flex;
  gap: 12px;
  overflow-x: auto;
  min-height: calc(100vh - 200px);
}
.kanban-column {
  flex: 1;
  min-width: 240px;
  background: var(--el-fill-color-light);
  border-radius: 8px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  transition: background 0.2s, border 0.2s;
  border: 2px solid transparent;
}
.kanban-column.drag-over {
  background: var(--el-color-primary-light-9);
  border-color: var(--el-color-primary);
}
.kanban-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--el-border-color);
}
.kanban-count {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  background: var(--el-border-color);
  border-radius: 10px;
  padding: 0 6px;
}
.kanban-cards {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.kanban-card {
  background: #fff;
  border-radius: 6px;
  padding: 12px;
  box-shadow: var(--shadow-card);
  cursor: pointer;
  transition: box-shadow 0.2s, opacity 0.2s;
  position: relative;
}
.kanban-card:hover {
  box-shadow: var(--shadow-pop);
}
.kanban-card.draggable {
  cursor: grab;
}
.kanban-card.dragging {
  opacity: 0.4;
}
.card-project {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-bottom: 4px;
}
.card-title {
  font-size: 14px;
  color: var(--el-text-color-primary);
  margin-bottom: 8px;
}
.card-meta {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.card-assignee {
  color: var(--el-color-primary);
  font-size: 12px;
}
.card-progress {
  height: 3px;
  background: var(--el-fill-color-light);
  border-radius: 2px;
  margin-top: 6px;
  overflow: hidden;
}
.card-progress__fill {
  height: 100%;
  background: var(--el-color-primary);
  border-radius: 2px;
}
.card-due.is-soon {
  color: var(--el-color-warning);
  font-weight: bold;
}
.card-due {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 4px;
}
.is-overdue {
  color: var(--el-color-danger);
  font-weight: bold;
}
.drag-hint {
  font-size: 10px;
  color: var(--el-text-color-placeholder);
  margin-top: 4px;
  display: none;
}
.kanban-card.draggable:hover .drag-hint {
  display: block;
}
</style>
