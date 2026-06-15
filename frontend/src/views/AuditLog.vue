<script setup>
import PageHeader from '../components/PageHeader.vue'
import EmptyState from '../components/EmptyState.vue'
import { ref, onMounted } from 'vue'
import { getAuditLogs } from '../api/audit'

const logs = ref([])
const total = ref(0)
const loading = ref(false)
const filters = ref({
  action: '',
  resource_type: '',
  start_date: '',
  end_date: '',
  page: 1,
  page_size: 50,
})

const ACTION_MAP = {
  login: '登录',
  create: '创建',
  update: '更新',
  delete: '删除',
  init: '立项',
  suspend: '暂停',
  resume: '恢复',
  assign: '指派',
  start: '开始',
  submit: '提交',
  approve: '审核通过',
  reject: '退回',
  permission_update: '权限变更',
  permission_reset: '权限重置',
}

const ACTION_TYPE = {
  login: '',
  create: 'success',
  update: 'primary',
  delete: 'danger',
  init: 'success',
  suspend: 'warning',
  resume: 'success',
  assign: 'primary',
  start: 'primary',
  submit: 'warning',
  approve: 'success',
  reject: 'danger',
  permission_update: 'warning',
  permission_reset: 'danger',
}

const RESOURCE_MAP = {
  project: '项目',
  task: '任务',
  user: '用户',
  customer: '客户',
  template: '模板',
  permission: '权限',
}

async function fetchLogs() {
  loading.value = true
  try {
    const params = { ...filters.value }
    if (!params.action) delete params.action
    if (!params.resource_type) delete params.resource_type
    if (!params.start_date) delete params.start_date
    if (!params.end_date) delete params.end_date
    const res = await getAuditLogs(params)
    logs.value = res.data.items
    total.value = res.data.total
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  filters.value.page = 1
  fetchLogs()
}

function handlePageChange(page) {
  filters.value.page = page
  fetchLogs()
}

function formatDetail(detail) {
  if (!detail) return '-'
  try {
    const obj = JSON.parse(detail)
    return Object.entries(obj).map(([k, v]) => `${k}: ${v}`).join('，')
  } catch {
    return detail
  }
}

onMounted(fetchLogs)
</script>

<template>
  <div>
    <PageHeader title="操作审计日志" />

    <el-card>
      <div style="display: flex; gap: 12px; margin-bottom: 16px; flex-wrap: wrap">
        <el-select v-model="filters.action" placeholder="操作类型" clearable style="width: 130px">
          <el-option v-for="(label, key) in ACTION_MAP" :key="key" :label="label" :value="key" />
        </el-select>
        <el-select v-model="filters.resource_type" placeholder="对象类型" clearable style="width: 110px">
          <el-option v-for="(label, key) in RESOURCE_MAP" :key="key" :label="label" :value="key" />
        </el-select>
        <el-date-picker
          v-model="filters.start_date"
          type="date"
          placeholder="开始日期"
          value-format="YYYY-MM-DD"
          style="width: 140px"
        />
        <el-date-picker
          v-model="filters.end_date"
          type="date"
          placeholder="结束日期"
          value-format="YYYY-MM-DD"
          style="width: 140px"
        />
        <el-button type="primary" @click="handleSearch">查询</el-button>
        <el-button @click="filters = { action: '', resource_type: '', start_date: '', end_date: '', page: 1, page_size: 50 }; fetchLogs()">重置</el-button>
      </div>

      <el-skeleton v-if="loading" :rows="6" animated style="padding: 8px 0" />
      <el-table v-else :data="logs" border stripe>
        <template #empty><EmptyState text="暂无审计记录" /></template>
        <el-table-column prop="created_at" label="时间" width="160">
          <template #default="{ row }">{{ row.created_at?.slice(0, 19).replace('T', ' ') }}</template>
        </el-table-column>
        <el-table-column prop="user_name" label="操作人" width="110" />
        <el-table-column prop="action" label="操作" width="110">
          <template #default="{ row }">
            <el-tag :type="ACTION_TYPE[row.action] || ''" size="small">
              {{ ACTION_MAP[row.action] || row.action }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="resource_type" label="对象类型" width="90">
          <template #default="{ row }">{{ RESOURCE_MAP[row.resource_type] || row.resource_type || '-' }}</template>
        </el-table-column>
        <el-table-column prop="resource_name" label="对象名称" min-width="160">
          <template #default="{ row }">{{ row.resource_name || '-' }}</template>
        </el-table-column>
        <el-table-column prop="detail" label="详情" min-width="200">
          <template #default="{ row }">
            <span style="color: #606266; font-size: 12px">{{ formatDetail(row.detail) }}</span>
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
  </div>
</template>
