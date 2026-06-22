<script setup>
import PageHeader from '../components/PageHeader.vue'
import { ref, computed, onMounted } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { PieChart, BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, TitleComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import { getOverview, getPhaseStats, getUserWorkload } from '../api/tasks'
import http from '../api/index'
import { PHASE_MAP, ROLE_MAP, STATUS_MAP } from '../utils/constants'

use([CanvasRenderer, PieChart, BarChart, GridComponent, TooltipComponent, LegendComponent, TitleComponent])

const overview = ref(null)
const phaseStats = ref({})
const workload = ref([])
const taskDist = ref([])
const productDist = ref([])
const deliveryCycle = ref([])
const returnRate = ref([])
const loading = ref(true)

onMounted(async () => {
  try {
    const [oRes, pRes, wRes, tRes, prRes, dcRes, rrRes] = await Promise.all([
      getOverview(),
      getPhaseStats(),
      getUserWorkload(),
      http.get('/dashboard/task-status-dist'),
      http.get('/dashboard/product-type-dist'),
      http.get('/dashboard/delivery-cycle'),
      http.get('/dashboard/return-rate'),
    ])
    overview.value = oRes.data
    phaseStats.value = pRes.data
    workload.value = wRes.data
    taskDist.value = tRes.data
    productDist.value = prRes.data
    deliveryCycle.value = dcRes.data
    returnRate.value = rrRes.data
  } finally {
    loading.value = false
  }
})

const STATUS_LABEL = { pending: '待处理', active: '进行中', review: '待审核', done: '已完成', paused: '已暂停', cancelled: '已取消', rework: '返工' }
const STATUS_COLOR = { pending: '#86909c', active: '#1890ff', review: '#d97706', done: '#16a34a', paused: '#c3c8ce', cancelled: '#c3c8ce', rework: '#dc2626' }
const PRODUCT_LABEL = { dia: 'DIA专线', transmission: '传输', dark_fiber: '裸纤', sdwan: 'SD-WAN' }
const PRODUCT_COLOR = { dia: '#1890ff', transmission: '#16a34a', dark_fiber: '#d97706', sdwan: '#dc2626' }

const taskPieOption = computed(() => ({
  tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
  legend: { bottom: 0, type: 'scroll' },
  series: [{
    type: 'pie',
    radius: ['40%', '70%'],
    data: taskDist.value.map(d => ({
      name: STATUS_LABEL[d.status] || d.status,
      value: d.count,
      itemStyle: { color: STATUS_COLOR[d.status] },
    })),
    label: { show: false },
  }],
}))

const productPieOption = computed(() => ({
  tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
  legend: { bottom: 0 },
  series: [{
    type: 'pie',
    radius: ['40%', '70%'],
    data: productDist.value.map(d => ({
      name: PRODUCT_LABEL[d.product_type] || d.product_type,
      value: d.count,
      itemStyle: { color: PRODUCT_COLOR[d.product_type] },
    })),
    label: { show: false },
  }],
}))

const phaseBarOption = computed(() => {
  const entries = Object.entries(phaseStats.value)
  const phases = entries.map(([k]) => PHASE_MAP[k] || k)
  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: { bottom: 0 },
    grid: { left: '3%', right: '4%', bottom: '10%', containLabel: true },
    xAxis: { type: 'category', data: phases, axisLabel: { rotate: 30, fontSize: 11 } },
    yAxis: { type: 'value', minInterval: 1 },
    series: [
      { name: '进行中', type: 'bar', stack: 'total', data: entries.map(([, v]) => v.active || 0), itemStyle: { color: '#1890ff' } },
      { name: '待审核', type: 'bar', stack: 'total', data: entries.map(([, v]) => v.review || 0), itemStyle: { color: '#d97706' } },
      { name: '已完成', type: 'bar', stack: 'total', data: entries.map(([, v]) => v.done || 0), itemStyle: { color: '#16a34a' } },
      { name: '待处理', type: 'bar', stack: 'total', data: entries.map(([, v]) => v.pending || 0), itemStyle: { color: '#c3c8ce' } },
    ],
  }
})

const deliveryCycleOption = computed(() => ({
  tooltip: { trigger: 'axis', formatter: (params) => `${params[0].name}<br/>平均 ${params[0].value} 天 (${deliveryCycle.value.find(d => (PHASE_MAP[d.phase] || d.phase) === params[0].name)?.sample_count || 0} 个任务)` },
  grid: { left: '3%', right: '8%', bottom: '3%', containLabel: true },
  xAxis: { type: 'value', name: '天', nameLocation: 'end' },
  yAxis: { type: 'category', data: deliveryCycle.value.map(d => PHASE_MAP[d.phase] || d.phase) },
  series: [{
    type: 'bar',
    data: deliveryCycle.value.map(d => ({
      value: d.avg_days,
      itemStyle: { color: d.avg_days > 7 ? '#dc2626' : d.avg_days > 3 ? '#d97706' : '#16a34a' },
    })),
    label: { show: true, position: 'right', formatter: (p) => `${p.value}天` },
  }],
}))

const returnRateOption = computed(() => ({
  tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
  legend: { bottom: 0 },
  grid: { left: '3%', right: '4%', bottom: '10%', containLabel: true },
  xAxis: { type: 'category', data: returnRate.value.map(d => PHASE_MAP[d.phase] || d.phase), axisLabel: { rotate: 30, fontSize: 11 } },
  yAxis: [
    { type: 'value', name: '退回率(%)', min: 0, max: 100 },
    { type: 'value', name: '平均次数' },
  ],
  series: [
    { name: '退回率', type: 'bar', yAxisIndex: 0, data: returnRate.value.map(d => d.rate), itemStyle: { color: '#dc2626' } },
    { name: '平均退回次数', type: 'line', yAxisIndex: 1, data: returnRate.value.map(d => d.avg_rework), itemStyle: { color: '#d97706' } },
  ],
}))

const workloadBarOption = computed(() => ({
  tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
  grid: { left: '3%', right: '8%', bottom: '3%', containLabel: true },
  xAxis: { type: 'value', minInterval: 1 },
  yAxis: { type: 'category', data: workload.value.map(u => u.display_name) },
  series: [{
    type: 'bar',
    data: workload.value.map(u => ({
      value: u.active_tasks,
      itemStyle: { color: u.active_tasks > 4 ? '#dc2626' : u.active_tasks > 2 ? '#d97706' : '#16a34a' },
    })),
    label: { show: true, position: 'right' },
  }],
}))
</script>

<template>
  <div v-loading="loading">
    <PageHeader title="报表中心" />

    <!-- Overview Cards -->
    <el-row :gutter="16" style="margin-bottom: 24px" v-if="overview">
      <el-col :span="6">
        <el-card shadow="hover">
          <div class="stat-card">
            <div class="stat-number" style="color: var(--el-text-color-secondary)">{{ overview.projects.draft }}</div>
            <div class="stat-label">草稿项目</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <div class="stat-card">
            <div class="stat-number" style="color: var(--el-color-primary)">{{ overview.projects.active }}</div>
            <div class="stat-label">进行中项目</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <div class="stat-card">
            <div class="stat-number" style="color: var(--el-color-success)">{{ overview.projects.completed }}</div>
            <div class="stat-label">已完成项目</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <div class="stat-card">
            <div class="stat-number" style="color: var(--el-color-danger)">{{ overview.overdue_tasks }}</div>
            <div class="stat-label">超期任务</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Pie Charts Row -->
    <el-row :gutter="16" style="margin-bottom: 24px">
      <el-col :span="12">
        <el-card>
          <template #header>任务状态分布</template>
          <v-chart :option="taskPieOption" style="height: 240px" autoresize />
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card>
          <template #header>产品线项目分布</template>
          <v-chart :option="productPieOption" style="height: 240px" autoresize />
        </el-card>
      </el-col>
    </el-row>

    <!-- Phase Bar Chart -->
    <el-card style="margin-bottom: 24px">
      <template #header>各阶段任务分布</template>
      <v-chart :option="phaseBarOption" style="height: 280px" autoresize />
    </el-card>

    <!-- Delivery Cycle Charts -->
    <el-row :gutter="16" style="margin-bottom: 24px">
      <el-col :span="12">
        <el-card>
          <template #header>各阶段平均停留时长（天）</template>
          <div v-if="deliveryCycle.length === 0" style="text-align: center; color: var(--el-text-color-secondary); padding: 40px 0">暂无已完成任务数据</div>
          <v-chart v-else :option="deliveryCycleOption" :style="{ height: Math.max(deliveryCycle.length * 36 + 60, 160) + 'px' }" autoresize />
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card>
          <template #header>各阶段退回率</template>
          <div v-if="returnRate.length === 0" style="text-align: center; color: var(--el-text-color-secondary); padding: 40px 0">暂无数据</div>
          <v-chart v-else :option="returnRateOption" style="height: 260px" autoresize />
        </el-card>
      </el-col>
    </el-row>

    <!-- Workload Bar Chart -->
    <el-row :gutter="16">
      <el-col :span="10">
        <el-card>
          <template #header>人员负荷 (进行中+待审核)</template>
          <div v-if="workload.length === 0" style="text-align: center; color: var(--el-text-color-secondary); padding: 40px 0">
            暂无数据
          </div>
          <v-chart v-else :option="workloadBarOption" :style="{ height: Math.max(workload.length * 40 + 40, 120) + 'px' }" autoresize />
        </el-card>
      </el-col>

      <!-- Phase Stats Table -->
      <el-col :span="14">
        <el-card>
          <template #header>阶段详情表</template>
          <el-table stripe :data="Object.entries(phaseStats).map(([k, v]) => ({ phase: k, ...v }))" size="small">
            <el-table-column label="阶段" width="110">
              <template #default="{ row }">{{ PHASE_MAP[row.phase] || row.phase }}</template>
            </el-table-column>
            <el-table-column prop="total" label="总数" width="55" align="center" />
            <el-table-column label="完成率" min-width="130">
              <template #default="{ row }">
                <el-progress
                  :percentage="row.total ? Math.round(row.done / row.total * 100) : 0"
                  :stroke-width="12"
                  :text-inside="true"
                />
              </template>
            </el-table-column>
            <el-table-column prop="active" label="进行中" width="65" align="center">
              <template #default="{ row }"><span style="color: var(--el-color-primary)">{{ row.active }}</span></template>
            </el-table-column>
            <el-table-column prop="overdue" label="超期" width="55" align="center">
              <template #default="{ row }">
                <span :style="{ color: row.overdue ? 'var(--el-color-danger)' : 'var(--el-text-color-secondary)', fontWeight: row.overdue ? 'bold' : 'normal' }">{{ row.overdue }}</span>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.stat-card { text-align: center; padding: 8px 0; }
.stat-number { font-size: 32px; font-weight: bold; }
.stat-label { font-size: 14px; color: var(--el-text-color-secondary); margin-top: 4px; }
</style>
