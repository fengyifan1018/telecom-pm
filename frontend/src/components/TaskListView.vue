<script setup>
import { ref, watch, computed } from 'vue'
import { listTasks, startTask, submitTask, approveTask, rejectTask, updateTask } from '../api/tasks'
import TaskDrawer from './TaskDrawer.vue'
import { STATUS_MAP, PHASE_MAP, PRIORITY_MAP, PRIORITY_OPTIONS } from '../utils/constants'
import { todayStr } from '../utils/format'
import { useAuthStore } from '../stores/auth'
import { ElMessage, ElMessageBox } from 'element-plus'

const props = defineProps({
  filters: { type: Object, default: () => ({}) },
})

const auth = useAuthStore()
const tasks = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const sort = ref('')
const order = ref('asc')
const loading = ref(false)

const drawerVisible = ref(false)
const selectedTask = ref(null)
const rowLoading = ref({})

function buildParams() {
  const f = props.filters || {}
  const params = {
    page: page.value,
    page_size: pageSize.value,
  }
  if (f.project_id) params.project_id = f.project_id
  if (f.phase) params.phase = f.phase
  if (f.assignee_id) params.assignee_id = f.assignee_id
  if (f.keyword) params.keyword = f.keyword
  if (f.priority) params.priority = f.priority
  if (f.overdue) params.overdue = true
  if (Array.isArray(f.status) && f.status.length) params.status = f.status.join(',')
  if (sort.value) { params.sort = sort.value; params.order = order.value }
  return params
}

async function fetchData() {
  loading.value = true
  try {
    const res = await listTasks(buildParams())
    tasks.value = res.data.items
    total.value = res.data.total
  } finally {
    loading.value = false
  }
}

// 筛选变化回到第一页重新查询
watch(() => props.filters, () => { page.value = 1; fetchData() }, { deep: true, immediate: true })

function onSortChange({ prop, order: ord }) {
  if (!ord) { sort.value = ''; order.value = 'asc' }
  else { sort.value = prop; order.value = ord === 'descending' ? 'desc' : 'asc' }
  page.value = 1
  fetchData()
}

function onPageChange(p) { page.value = p; fetchData() }

function openTask(row) { selectedTask.value = row; drawerVisible.value = true }

function isOverdue(row) {
  return row.planned_end && row.planned_end < todayStr() && !['done', 'cancelled'].includes(row.status)
}

const canStart = (row) => {
  const role = auth.user?.role
  return role === 'pm' || role === 'admin' || row.assignee_id === auth.user?.id
}

async function runAction(row, fn, okMsg) {
  rowLoading.value = { ...rowLoading.value, [row.id]: true }
  try {
    await fn(row.id)
    ElMessage.success(okMsg)
    await fetchData()
  } catch (e) {
    // 错误提示由全局拦截器统一处理
  } finally {
    rowLoading.value = { ...rowLoading.value, [row.id]: false }
  }
}

function handleStart(row) { runAction(row, startTask, '任务已开始') }
function handleSubmit(row) { runAction(row, (id) => submitTask(id), '已提交审核') }
function handleApprove(row) { runAction(row, approveTask, '审核通过') }

async function handleReject(row) {
  try {
    const { value } = await ElMessageBox.prompt('请输入退回原因', '退回任务', {
      confirmButtonText: '确认退回', cancelButtonText: '取消',
      inputValidator: (v) => !!v || '请输入退回原因',
    })
    await runAction(row, (id) => rejectTask(id, value), '已退回')
  } catch (e) { /* 取消无需提示 */ }
}

function onRefresh() { fetchData() }

// 抽屉内上一条/下一条导航
function onNavigate(id) {
  const t = tasks.value.find(t => t.id === id)
  if (t) selectedTask.value = t
}

// 单元格点击进入编辑态（PM/管理员或负责人可编辑截止/优先级）
const editingCell = ref('')
function startEdit(row, field) {
  if (canStart(row)) editingCell.value = `${row.id}:${field}`
}
function stopEdit() { editingCell.value = '' }
async function saveField(row, patch) {
  if (patch.planned_end === null || patch.priority === null) { stopEdit(); return }
  try {
    await updateTask(row.id, patch)
    ElMessage.success('已保存')
    Object.assign(row, patch)
  } catch {
    // 错误提示由全局拦截器统一处理
  } finally {
    stopEdit()
  }
}
</script>

<template>
  <div v-loading="loading">
    <el-table stripe :data="tasks" size="small" @row-click="openTask" @sort-change="onSortChange"
              highlight-current-row style="cursor: pointer">
      <el-table-column prop="task_no" label="编号" width="160" />
      <el-table-column prop="title" label="标题" min-width="200" show-overflow-tooltip />
      <el-table-column prop="project_name" label="项目" width="140" show-overflow-tooltip />
      <el-table-column label="阶段" width="100">
        <template #default="{ row }">{{ PHASE_MAP[row.phase] || row.phase }}</template>
      </el-table-column>
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="STATUS_MAP[row.status]?.type" size="small">{{ STATUS_MAP[row.status]?.label }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="进度" width="110" class-name="col-progress">
        <template #default="{ row }">
          <div class="progress-cell">
            <el-progress :percentage="row.progress || 0" :stroke-width="6" :show-text="false" style="width: 60px" />
            <span class="progress-cell__num">{{ row.progress || 0 }}%</span>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="负责人" width="90">
        <template #default="{ row }">{{ row.assignee_name || '—' }}</template>
      </el-table-column>
      <el-table-column label="优先级" width="90" prop="priority" sortable="custom">
        <template #default="{ row }">
          <div v-if="editingCell === `${row.id}:priority`" @click.stop>
            <el-select :model-value="row.priority" size="small" style="width: 80px" @change="(v) => saveField(row, { priority: v })"
                       @visible-change="(v) => { if (!v) stopEdit() }">
              <el-option v-for="o in PRIORITY_OPTIONS" :key="o.value" :label="o.label" :value="o.value" />
            </el-select>
          </div>
          <el-tag v-else-if="PRIORITY_MAP[row.priority]" :type="PRIORITY_MAP[row.priority].type" size="small"
                  :style="canStart(row) ? 'cursor: pointer' : ''" @click.stop="startEdit(row, 'priority')">
            {{ PRIORITY_MAP[row.priority].label }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="截止" width="120" prop="planned_end" sortable="custom">
        <template #default="{ row }">
          <div v-if="editingCell === `${row.id}:planned_end`" @click.stop>
            <el-date-picker :model-value="row.planned_end" type="date" size="small" value-format="YYYY-MM-DD"
                            style="width: 110px" @change="(v) => saveField(row, { planned_end: v })" @blur="stopEdit" />
          </div>
          <span v-else @click.stop="startEdit(row, 'planned_end')"
                :style="{ color: isOverdue(row) ? '#f56c6c' : '', fontWeight: isOverdue(row) ? 'bold' : '', cursor: canStart(row) ? 'pointer' : '' }">
            {{ row.planned_end || '—' }}
          </span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="150" fixed="right">
        <template #default="{ row }">
          <el-button v-if="row.status === 'pending' && canStart(row)" size="small" type="primary"
                     :loading="rowLoading[row.id]" @click.stop="handleStart(row)">开始</el-button>
          <el-button v-else-if="row.status === 'active'" size="small" type="primary"
                     :loading="rowLoading[row.id]" @click.stop="handleSubmit(row)">提交</el-button>
          <template v-else-if="row.status === 'review'">
            <el-button size="small" type="success" :loading="rowLoading[row.id]" @click.stop="handleApprove(row)">通过</el-button>
            <el-button size="small" type="warning" :loading="rowLoading[row.id]" @click.stop="handleReject(row)">退回</el-button>
          </template>
        </template>
      </el-table-column>
    </el-table>

    <div style="display: flex; justify-content: flex-end; margin-top: 12px">
      <el-pagination
        layout="total, prev, pager, next"
        :total="total"
        :page-size="pageSize"
        :current-page="page"
        @current-change="onPageChange"
      />
    </div>

    <TaskDrawer v-model:visible="drawerVisible" :task="selectedTask" show-project-link
                :peer-ids="tasks.map(t => t.id)" @navigate="onNavigate"
                @refresh="onRefresh" @view-project="(id) => $router.push(`/projects/${id}`)" />
  </div>
</template>

<style scoped>
.progress-cell {
  display: flex;
  align-items: center;
  gap: 6px;
}
.progress-cell__num {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  font-variant-numeric: tabular-nums;
}
@media (max-width: 767px) {
  :deep(.col-progress) {
    display: none;
  }
}
</style>
