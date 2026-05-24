<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { getDashboard, listTasks } from '../api/tasks'
import { STATUS_MAP, PHASE_MAP } from '../utils/constants'

const router = useRouter()
const auth = useAuthStore()
const today = new Date().toISOString().slice(0, 10)
const stats = ref({ pending: 0, active: 0, review: 0, done: 0, overdue: 0 })
const myTasks = ref([])
const reviewTasks = ref([])
const overdueTasks = ref([])
const loading = ref(true)
const activeTab = ref('active')

onMounted(async () => {
  try {
    const [dashRes, taskRes, reviewRes, activeRes, reviewRes2] = await Promise.all([
      getDashboard(),
      listTasks({ assignee_id: auth.user?.id, status: 'active', page_size: 20 }),
      listTasks({ assignee_id: auth.user?.id, status: 'review', page_size: 20 }),
      listTasks({ assignee_id: auth.user?.id, status: 'active', page_size: 100 }),
      listTasks({ assignee_id: auth.user?.id, status: 'review', page_size: 100 }),
    ])
    stats.value = dashRes.data
    myTasks.value = taskRes.data.items
    reviewTasks.value = reviewRes.data.items
    const allMyTasks = [...activeRes.data.items, ...reviewRes2.data.items]
    overdueTasks.value = allMyTasks.filter(t => t.planned_end && t.planned_end < today)
  } finally {
    loading.value = false
  }
})

function goProject(task) {
  router.push(`/projects/${task.project_id}`)
}

function isOverdue(task) {
  return task.planned_end && task.planned_end < new Date().toISOString().slice(0, 10)
}
</script>

<template>
  <div v-loading="loading">
    <h3 style="margin-top: 0">工作台</h3>

    <el-row :gutter="12" style="margin-bottom: 16px">
      <el-col :xs="12" :span="6">
        <el-card shadow="hover">
          <div class="stat-card">
            <div class="stat-number" style="color: #409eff">{{ stats.active }}</div>
            <div class="stat-label">进行中</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :span="6">
        <el-card shadow="hover">
          <div class="stat-card">
            <div class="stat-number" style="color: #e6a23c">{{ stats.review }}</div>
            <div class="stat-label">待审核</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :span="6" style="margin-top: 0">
        <el-card shadow="hover">
          <div class="stat-card">
            <div class="stat-number" style="color: #67c23a">{{ stats.done }}</div>
            <div class="stat-label">已完成</div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :span="6">
        <el-card shadow="hover" style="cursor: pointer" @click="activeTab = 'overdue'">
          <div class="stat-card">
            <div class="stat-number" style="color: #f56c6c">{{ stats.overdue }}</div>
            <div class="stat-label">超期</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card>
      <el-tabs v-model="activeTab">
        <el-tab-pane :label="`进行中 (${myTasks.length})`" name="active">
          <el-table :data="myTasks" style="width: 100%" @row-click="goProject" highlight-current-row size="small">
            <el-table-column prop="task_no" label="编号" width="160" class-name="col-task-no" />
            <el-table-column prop="title" label="任务" min-width="180" />
            <el-table-column label="阶段" width="100">
              <template #default="{ row }">{{ PHASE_MAP[row.phase] || row.phase }}</template>
            </el-table-column>
            <el-table-column label="截止" width="110">
              <template #default="{ row }">
                <span :style="{ color: isOverdue(row) ? '#f56c6c' : '', fontWeight: isOverdue(row) ? 'bold' : '' }">
                  {{ row.planned_end || '-' }}
                </span>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="myTasks.length === 0" description="暂无进行中的任务" :image-size="60" />
        </el-tab-pane>
        <el-tab-pane :label="`待审核 (${reviewTasks.length})`" name="review">
          <el-table :data="reviewTasks" style="width: 100%" @row-click="goProject" highlight-current-row size="small">
            <el-table-column prop="task_no" label="编号" width="160" class-name="col-task-no" />
            <el-table-column prop="title" label="任务" min-width="180" />
            <el-table-column label="阶段" width="100">
              <template #default="{ row }">{{ PHASE_MAP[row.phase] || row.phase }}</template>
            </el-table-column>
            <el-table-column prop="planned_end" label="截止" width="110" />
          </el-table>
          <el-empty v-if="reviewTasks.length === 0" description="暂无待审核任务" :image-size="60" />
        </el-tab-pane>
        <el-tab-pane name="overdue">
          <template #label>
            <span :style="{ color: overdueTasks.length ? '#f56c6c' : '' }">
              超期 ({{ overdueTasks.length }})
            </span>
          </template>
          <el-table :data="overdueTasks" style="width: 100%" @row-click="goProject" highlight-current-row size="small">
            <el-table-column prop="task_no" label="编号" width="160" class-name="col-task-no" />
            <el-table-column prop="title" label="任务" min-width="180" />
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
                <span style="color: #f56c6c; font-weight: bold">{{ row.planned_end }}</span>
                <span style="color: #f56c6c; font-size: 11px; margin-left: 4px">
                  (超{{ Math.floor((new Date(today) - new Date(row.planned_end)) / 86400000) }}天)
                </span>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="overdueTasks.length === 0" description="暂无超期任务" :image-size="60" />
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<style scoped>
.stat-card { text-align: center; padding: 8px 0; }
.stat-number { font-size: 32px; font-weight: bold; }
.stat-label { font-size: 14px; color: #909399; margin-top: 4px; }

@media (max-width: 767px) {
  .stat-number { font-size: 24px; }
  .el-row { row-gap: 10px; }
  /* hide task_no column on mobile */
  :deep(.col-task-no) { display: none; }
}
</style>
