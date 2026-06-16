<script setup>
import PageHeader from '../components/PageHeader.vue'
import EmptyState from '../components/EmptyState.vue'
import TaskListView from '../components/TaskListView.vue'
import { todayStr } from '../utils/format'
import { ref, computed, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { listTasks, startTask, submitTask, approveTask, listUsers } from '../api/tasks'
import { listProjects } from '../api/projects'
import { STATUS_MAP, PHASE_MAP } from '../utils/constants'
import { ElMessage } from 'element-plus'

const router = useRouter()
const tasks = ref([])
const projects = ref([])
const users = ref([])
const loading = ref(true)

// 视图模式（持久化）
const viewMode = ref(localStorage.getItem('task-view-mode') || 'kanban')
watch(viewMode, (v) => localStorage.setItem('task-view-mode', v))

// 共享筛选
const filterProject = ref('')
const filterPhase = ref('')
const filterAssignee = ref('')
const filterKeyword = ref('')
const filterPriority = ref('')
const filterOverdue = ref(false)
const filterStatus = ref([]) // 仅列表视图用

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

// 看板取数：服务端筛选（不传 status，列本身即状态）
async function fetchKanban() {
  loading.value = true
  try {
    const params = { page_size: 200 }
    if (filterProject.value) params.project_id = filterProject.value
    if (filterPhase.value) params.phase = filterPhase.value
    if (filterAssignee.value) params.assignee_id = filterAssignee.value
    if (filterKeyword.value) params.keyword = filterKeyword.value
    if (filterPriority.value) params.priority = filterPriority.value
    if (filterOverdue.value) params.overdue = true
    const tRes = await listTasks(params)
    tasks.value = tRes.data.items
  } finally {
    loading.value = false
  }
}

// 仅看板模式下，筛选变化时重新取数
watch([filterProject, filterPhase, filterAssignee, filterKeyword, filterPriority, filterOverdue], () => {
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
            <div v-if="task.planned_end" class="card-due" :class="{ 'is-overdue': task.planned_end < todayStr() && col.key !== 'done' }">
              {{ task.planned_end }}
            </div>
            <div v-if="VALID_TRANSITIONS[task.status]" class="drag-hint">拖拽→{{ STATUS_MAP[VALID_TRANSITIONS[task.status].target]?.label }}</div>
          </div>
          <EmptyState v-if="col.tasks.length === 0" text="" :size="28" />
        </div>
      </div>
    </div>
    <TaskListView v-else :filters="listFilters" />
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
  background: #f5f7fa;
  border-radius: 8px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  transition: background 0.2s, border 0.2s;
  border: 2px solid transparent;
}
.kanban-column.drag-over {
  background: #ecf5ff;
  border-color: #409eff;
}
.kanban-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid #e4e7ed;
}
.kanban-count {
  font-size: 12px;
  color: #909399;
  background: #e4e7ed;
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
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
  cursor: pointer;
  transition: box-shadow 0.2s, opacity 0.2s;
  position: relative;
}
.kanban-card:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
}
.kanban-card.draggable {
  cursor: grab;
}
.kanban-card.dragging {
  opacity: 0.4;
}
.card-project {
  font-size: 11px;
  color: #909399;
  margin-bottom: 4px;
}
.card-title {
  font-size: 14px;
  color: #303133;
  margin-bottom: 8px;
}
.card-meta {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #909399;
}
.card-assignee {
  color: #409eff;
  font-size: 11px;
}
.card-due {
  font-size: 11px;
  color: #909399;
  margin-top: 4px;
}
.is-overdue {
  color: #f56c6c;
  font-weight: bold;
}
.drag-hint {
  font-size: 10px;
  color: #c0c4cc;
  margin-top: 4px;
  display: none;
}
.kanban-card.draggable:hover .drag-hint {
  display: block;
}
</style>
