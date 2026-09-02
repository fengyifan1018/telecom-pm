<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { getDashboard, listTasks } from '../api/tasks'
import { STATUS_MAP, PHASE_MAP } from '../utils/constants'
import PageHeader from '../components/PageHeader.vue'
import EmptyState from '../components/EmptyState.vue'
import TaskDrawer from '../components/TaskDrawer.vue'
import { todayStr, overdueDays } from '../utils/format'

const router = useRouter()
const auth = useAuthStore()
const today = todayStr()
// 全局/我的视图切换（仅管理员/项目经理/运营可看全局）
const canGlobal = ['admin', 'pm', 'operations'].includes(auth.user?.role)
const scope = ref('mine')
const stats = ref({ pending: 0, active: 0, review: 0, done: 0, overdue: 0 })
const myTasks = ref([])
const reviewTasks = ref([])
const doneTasks = ref([])
const overdueTasks = ref([])
const loading = ref(true)
const activeTab = ref('active')
const drawerVisible = ref(false)
const selectedTask = ref(null)

const assigneeFilter = computed(() => (scope.value === 'mine' ? auth.user?.id : undefined))

const statCards = computed(() => [
  { key: 'active', label: '进行中', value: stats.value.active, color: 'var(--el-color-primary)' },
  { key: 'review', label: '待审核', value: stats.value.review, color: 'var(--el-color-warning)' },
  { key: 'done', label: '已完成', value: stats.value.done, color: 'var(--el-color-success)' },
  { key: 'overdue', label: '超期', value: stats.value.overdue, color: 'var(--el-color-danger)' },
])

async function loadData() {
  loading.value = true
  try {
    const [dashRes, taskRes, reviewRes, doneRes, activeRes, reviewRes2] = await Promise.all([
      getDashboard({ scope: scope.value }),
      listTasks({ assignee_id: assigneeFilter.value, status: 'active', page_size: 20 }),
      listTasks({ assignee_id: assigneeFilter.value, status: 'review', page_size: 20 }),
      listTasks({ assignee_id: assigneeFilter.value, status: 'done', page_size: 20 }),
      listTasks({ assignee_id: assigneeFilter.value, status: 'active', page_size: 100 }),
      listTasks({ assignee_id: assigneeFilter.value, status: 'review', page_size: 100 }),
    ])
    stats.value = dashRes.data
    myTasks.value = taskRes.data.items
    reviewTasks.value = reviewRes.data.items
    doneTasks.value = doneRes.data.items
    const allMyTasks = [...activeRes.data.items, ...reviewRes2.data.items]
    overdueTasks.value = allMyTasks.filter(t => t.planned_end && t.planned_end < today)
  } finally {
    loading.value = false
  }
}

watch(scope, loadData)
onMounted(loadData)

function openTask(task) {
  selectedTask.value = task
  drawerVisible.value = true
}

// 抽屉导航：跟随当前激活 tab 的任务序列
const drawerPeerIds = computed(() => {
  const map = { active: myTasks, review: reviewTasks, done: doneTasks, overdue: overdueTasks }
  return (map[activeTab.value]?.value || []).map(t => t.id)
})
function onNavigate(id) {
  const map = { active: myTasks, review: reviewTasks, done: doneTasks, overdue: overdueTasks }
  const t = (map[activeTab.value]?.value || []).find(t => t.id === id)
  if (t) selectedTask.value = t
}

function goProject(projectId) {
  drawerVisible.value = false
  router.push(`/projects/${projectId}`)
}

function isOverdue(task) {
  return task.planned_end && task.planned_end < today
}
</script>

<template>
  <div v-loading="loading">
    <PageHeader title="工作台">
      <el-radio-group v-if="canGlobal" v-model="scope" size="small">
        <el-radio-button value="mine">我的</el-radio-button>
        <el-radio-button value="all">全局</el-radio-button>
      </el-radio-group>
    </PageHeader>

    <el-row :gutter="12" style="margin-bottom: 16px">
      <el-col v-for="c in statCards" :key="c.key" :xs="12" :span="6">
        <el-card
          shadow="hover"
          class="stat-card-clickable"
          :style="activeTab === c.key ? { borderColor: c.color, boxShadow: `0 2px 12px ${c.color}40` } : {}"
          @click="activeTab = c.key"
        >
          <div class="stat-card">
            <div class="stat-number" :style="{ color: c.color }">{{ c.value }}</div>
            <div class="stat-label">{{ c.label }}</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card>
      <el-tabs v-model="activeTab">
        <el-tab-pane :label="`进行中 (${myTasks.length})`" name="active">
          <el-table v-if="myTasks.length" stripe :data="myTasks" style="width: 100%" @row-click="openTask" highlight-current-row size="small">
            <el-table-column prop="task_no" label="编号" width="160" class-name="col-task-no" />
            <el-table-column prop="title" label="任务" min-width="180" show-overflow-tooltip/>
            <el-table-column v-if="scope === 'all'" label="负责人" width="110">
              <template #default="{ row }">{{ row.assignee_name || '—' }}</template>
            </el-table-column>
            <el-table-column label="阶段" width="100">
              <template #default="{ row }">{{ PHASE_MAP[row.phase] || row.phase }}</template>
            </el-table-column>
            <el-table-column label="截止" width="110">
              <template #default="{ row }">
                <span :style="{ color: isOverdue(row) ? 'var(--el-color-danger)' : '', fontWeight: isOverdue(row) ? 'bold' : '' }">
                  {{ row.planned_end || '-' }}
                </span>
              </template>
            </el-table-column>
          </el-table>
          <EmptyState v-else text="暂无进行中的任务">
            <el-button v-if="scope === 'mine'" type="primary" size="small" @click="router.push('/kanban')">去任务页领任务</el-button>
          </EmptyState>
        </el-tab-pane>
        <el-tab-pane :label="`待审核 (${reviewTasks.length})`" name="review">
          <el-table v-if="reviewTasks.length" stripe :data="reviewTasks" style="width: 100%" @row-click="openTask" highlight-current-row size="small">
            <el-table-column prop="task_no" label="编号" width="160" class-name="col-task-no" />
            <el-table-column prop="title" label="任务" min-width="180" show-overflow-tooltip/>
            <el-table-column v-if="scope === 'all'" label="负责人" width="110">
              <template #default="{ row }">{{ row.assignee_name || '—' }}</template>
            </el-table-column>
            <el-table-column label="阶段" width="100">
              <template #default="{ row }">{{ PHASE_MAP[row.phase] || row.phase }}</template>
            </el-table-column>
            <el-table-column prop="planned_end" label="截止" width="110" />
          </el-table>
          <EmptyState v-else text="暂无待审核任务" />
        </el-tab-pane>
        <el-tab-pane :label="`已完成 (${doneTasks.length})`" name="done">
          <el-table v-if="doneTasks.length" stripe :data="doneTasks" style="width: 100%" @row-click="openTask" highlight-current-row size="small">
            <el-table-column prop="task_no" label="编号" width="160" class-name="col-task-no" />
            <el-table-column prop="title" label="任务" min-width="180" show-overflow-tooltip/>
            <el-table-column v-if="scope === 'all'" label="负责人" width="110">
              <template #default="{ row }">{{ row.assignee_name || '—' }}</template>
            </el-table-column>
            <el-table-column label="阶段" width="100">
              <template #default="{ row }">{{ PHASE_MAP[row.phase] || row.phase }}</template>
            </el-table-column>
            <el-table-column prop="planned_end" label="截止" width="110" />
          </el-table>
          <EmptyState v-else text="暂无已完成任务" />
        </el-tab-pane>
        <el-tab-pane name="overdue">
          <template #label>
            <span :style="{ color: overdueTasks.length ? 'var(--el-color-danger)' : '' }">
              超期 ({{ overdueTasks.length }})
            </span>
          </template>
          <el-table v-if="overdueTasks.length" stripe :data="overdueTasks" style="width: 100%" @row-click="openTask" highlight-current-row size="small">
            <el-table-column prop="task_no" label="编号" width="160" class-name="col-task-no" />
            <el-table-column prop="title" label="任务" min-width="180" show-overflow-tooltip/>
            <el-table-column v-if="scope === 'all'" label="负责人" width="110">
              <template #default="{ row }">{{ row.assignee_name || '—' }}</template>
            </el-table-column>
            <el-table-column label="阶段" width="100">
              <template #default="{ row }">{{ PHASE_MAP[row.phase] || row.phase }}</template>
            </el-table-column>
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <el-tag :type="STATUS_MAP[row.status]?.type" size="small">{{ STATUS_MAP[row.status]?.label }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="截止日期" width="120">
              <template #default="{ row }">
                <span style="color: var(--el-color-danger); font-weight: bold">{{ row.planned_end }}</span>
                <span style="color: var(--el-color-danger); font-size: 11px; margin-left: 4px">
                  (超{{ overdueDays(row.planned_end) }}天)
                </span>
              </template>
            </el-table-column>
          </el-table>
          <EmptyState v-else text="暂无超期任务" />
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <TaskDrawer
      v-model:visible="drawerVisible"
      :task="selectedTask"
      show-project-link
      :peer-ids="drawerPeerIds"
      @navigate="onNavigate"
      @view-project="goProject"
      @refresh="loadData"
    />
  </div>
</template>

<style scoped>
.stat-card { text-align: center; padding: 8px 0; }
.stat-number { font-size: 32px; font-weight: bold; }
.stat-label { font-size: 14px; color: var(--el-text-color-secondary); margin-top: 4px; }

.stat-card-clickable {
  cursor: pointer;
  transition: box-shadow 0.2s, border-color 0.2s;
}

@media (max-width: 767px) {
  .stat-number { font-size: 24px; }
  .el-row { row-gap: 10px; }
  /* hide task_no column on mobile */
  :deep(.col-task-no) { display: none; }
}
</style>
