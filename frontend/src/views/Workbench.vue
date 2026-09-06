<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useAuthStore } from '../stores/auth'
import { getWorkbench } from '../api/tasks'
import { STATUS_MAP, PRIORITY_MAP } from '../utils/constants'
import { timeAgo } from '../utils/format'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { PieChart } from 'echarts/charts'
import { TooltipComponent, LegendComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import { Suitcase, FolderOpened, CircleCheck, List, DataAnalysis, AlarmClock } from '@element-plus/icons-vue'

use([CanvasRenderer, PieChart, TooltipComponent, LegendComponent])

const auth = useAuthStore()
const canGlobal = ['admin', 'pm', 'operations'].includes(auth.user?.role)
// 全局角色默认看全局视图，其余角色固定个人视图
const scope = ref(canGlobal ? 'all' : 'mine')
const wb = ref(null)
const loading = ref(true)

// 欢迎横幅
const greeting = computed(() => {
  const h = new Date().getHours()
  if (h < 6) return '夜深了'
  if (h < 12) return '早上好'
  if (h < 14) return '中午好'
  if (h < 18) return '下午好'
  return '晚上好'
})
const dateLine = computed(() => {
  const d = new Date()
  const weeks = ['日', '一', '二', '三', '四', '五', '六']
  return `今天是 ${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日 星期${weeks[d.getDay()]}`
})

const stats = computed(() => wb.value?.stats || {})
const health = computed(() => wb.value?.project_health || {})

const statCards = computed(() => wb.value ? [
  { label: '项目总数', value: stats.value.project_total, icon: Suitcase, color: 'var(--el-color-primary)' },
  { label: '进行中项目', value: stats.value.project_active, icon: FolderOpened, color: 'var(--el-color-warning)' },
  { label: '已完成项目', value: stats.value.project_completed, icon: CircleCheck, color: 'var(--el-color-success)' },
  { label: '总任务数', value: stats.value.task_total, icon: List, color: 'var(--el-color-info)' },
  { label: '任务完成率', value: stats.value.completion_pct + '%', icon: DataAnalysis, color: 'var(--el-color-primary)' },
  { label: '延期任务', value: stats.value.task_overdue, icon: AlarmClock, color: 'var(--el-color-danger)' },
] : [])

async function load() {
  loading.value = true
  try {
    const res = await getWorkbench(scope.value === 'all' ? { scope: 'all' } : {})
    wb.value = res.data
  } finally {
    loading.value = false
  }
}
watch(scope, load)
onMounted(load)

// ── 环形图 ──
const RING_COLORS = {
  normal: '#16a34a', at_risk: '#dc2626', delayed: '#d97706', completed: '#8b5cf6',
  pending: '#86909c', active: '#1890ff', review: '#d97706', done: '#16a34a',
  blocked: '#dc2626', paused: '#d97706', cancelled: '#c8cdd4',
}
const projectRingOption = computed(() => {
  const h = health.value
  return {
    tooltip: { trigger: 'item' },
    series: [{
      type: 'pie', radius: ['70%', '92%'], label: { show: false },
      data: [
        { name: '正常', value: h.normal || 0, itemStyle: { color: RING_COLORS.normal } },
        { name: '有风险', value: h.at_risk || 0, itemStyle: { color: RING_COLORS.at_risk } },
        { name: '已延期', value: h.delayed || 0, itemStyle: { color: RING_COLORS.delayed } },
        { name: '已完成', value: h.completed || 0, itemStyle: { color: RING_COLORS.completed } },
      ].filter(d => d.value > 0),
    }],
  }
})
const projectLegend = computed(() => [
  { dot: RING_COLORS.normal, label: '进行中（正常）', value: health.value.normal || 0 },
  { dot: RING_COLORS.at_risk, label: '进行中（有风险）', value: health.value.at_risk || 0 },
  { dot: RING_COLORS.delayed, label: '进行中（已延期）', value: health.value.delayed || 0 },
  { dot: RING_COLORS.completed, label: '已完成', value: health.value.completed || 0 },
].filter(r => r.value > 0))

const taskRingOption = computed(() => ({
  tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
  series: [{
    type: 'pie', radius: ['70%', '92%'], label: { show: false },
    data: (wb.value?.task_status_dist || []).map(d => ({
      name: STATUS_MAP[d.status]?.label || d.status,
      value: d.count,
      itemStyle: { color: RING_COLORS[d.status] || '#c8cdd4' },
    })).filter(d => d.value > 0),
  }],
}))
const taskLegend = computed(() => (wb.value?.task_status_dist || []).map(d => ({
  dot: RING_COLORS[d.status] || '#c8cdd4',
  label: STATUS_MAP[d.status]?.label || d.status,
  value: d.count,
  pct: stats.value.task_total ? Math.round(d.count / stats.value.task_total * 100) : 0,
})))

const priorityTagType = (p) => PRIORITY_MAP[p]?.type || 'info'
const priorityLabel = (p) => PRIORITY_MAP[p]?.label || '-'
const severityTagType = (s) => (s === 'critical' || s === 'high' ? 'danger' : 'warning')
const severityLabel = (s) => ({ low: '低', medium: '中', high: '高', critical: '紧急' }[s] || s)
</script>

<template>
  <div v-loading="loading">
    <!-- 欢迎横幅 -->
    <div class="wb-greeting">
      <div>
        <h2 class="wb-greeting__title">{{ greeting }}，{{ auth.user?.display_name }} 👋</h2>
        <div class="wb-greeting__date">{{ dateLine }}</div>
      </div>
      <el-radio-group v-if="canGlobal" v-model="scope" size="small">
        <el-radio-button value="mine">我的</el-radio-button>
        <el-radio-button value="all">全局</el-radio-button>
      </el-radio-group>
    </div>

    <!-- 统计卡 -->
    <el-row :gutter="12" style="margin-bottom: 16px">
      <el-col v-for="c in statCards" :key="c.label" :xs="12" :span="4">
        <div class="ov-stat wb-stat">
          <div class="ov-stat__icon" :style="{ background: c.color }">
            <el-icon :size="20" color="#fff"><component :is="c.icon" /></el-icon>
          </div>
          <div>
            <div class="wb-stat__num num">{{ c.value }}</div>
            <div class="wb-stat__label">{{ c.label }}</div>
          </div>
        </div>
      </el-col>
    </el-row>

    <!-- 环形区 + 风险 -->
    <el-row :gutter="12" style="margin-bottom: 16px">
      <el-col :span="8">
        <el-card shadow="never" style="height: 100%">
          <div class="section-label">项目进度概览</div>
          <div style="display: flex; align-items: center; gap: 16px">
            <div style="position: relative; flex-shrink: 0">
              <v-chart :option="projectRingOption" style="width: 132px; height: 132px" autoresize />
              <div class="ring-center">
                <div class="ring-center__num num">{{ stats.completion_pct ?? 0 }}%</div>
                <div class="ring-center__label">任务完成率</div>
              </div>
            </div>
            <div style="flex: 1">
              <div v-for="r in projectLegend" :key="r.label" class="ring-legend-row">
                <span class="ring-dot" :style="{ background: r.dot }" />
                <span class="ring-legend-label">{{ r.label }}</span>
                <span class="ring-legend-value num">{{ r.value }} 个</span>
              </div>
              <div v-if="projectLegend.length === 0" style="color: var(--el-text-color-secondary); font-size: 13px">暂无项目</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="never" style="height: 100%">
          <div class="section-label">任务状态分布</div>
          <div style="display: flex; align-items: center; gap: 16px">
            <div style="position: relative; flex-shrink: 0">
              <v-chart :option="taskRingOption" style="width: 132px; height: 132px" autoresize />
              <div class="ring-center">
                <div class="ring-center__num num">{{ stats.task_total ?? 0 }}</div>
                <div class="ring-center__label">总任务</div>
              </div>
            </div>
            <div style="flex: 1">
              <div v-for="r in taskLegend" :key="r.label" class="ring-legend-row">
                <span class="ring-dot" :style="{ background: r.dot }" />
                <span class="ring-legend-label">{{ r.label }}</span>
                <span class="ring-legend-value num">{{ r.value }} ({{ r.pct }}%)</span>
              </div>
              <div v-if="taskLegend.length === 0" style="color: var(--el-text-color-secondary); font-size: 13px">暂无任务</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="never" style="height: 100%">
          <div class="section-label">风险预警 ({{ (wb?.risks || []).length }})</div>
          <template v-if="(wb?.risks || []).length">
            <div v-for="(r, i) in wb.risks" :key="i" class="ov-risk-item">
              <el-tag :type="severityTagType(r.severity)" size="small">{{ severityLabel(r.severity) }}</el-tag>
              <span class="ov-risk-title">
                {{ r.title }}
                <span class="ov-risk-meta">{{ r.task_no }}<template v-if="r.owner"> · {{ r.owner }}</template></span>
              </span>
            </div>
          </template>
          <div v-else style="color: var(--el-text-color-secondary); font-size: 13px">暂无风险项</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 在建项目 Top5 + 近期截止 -->
    <el-row :gutter="12" style="margin-bottom: 16px">
      <el-col :span="14">
        <el-card shadow="never" style="height: 100%">
          <div class="section-label">在建项目（按截止时间）</div>
          <template v-if="(wb?.top_projects || []).length">
            <div v-for="p in wb.top_projects" :key="p.project_id" class="top-project-row"
                 @click="$router.push(`/projects/${p.project_id}`)">
              <span class="top-project-name">{{ p.name }}</span>
              <div class="top-project-progress">
                <el-progress :percentage="p.progress_pct" :stroke-width="6" :show-text="false" style="width: 90px" />
                <span class="num" style="font-size: 12px; color: var(--el-text-color-secondary)">{{ p.progress_pct }}%</span>
              </div>
              <el-tag v-if="p.is_delayed" type="danger" size="small" effect="plain">已延期</el-tag>
              <span class="num" style="font-size: 12px; color: var(--el-text-color-placeholder)">{{ p.planned_end || '—' }}</span>
            </div>
          </template>
          <div v-else style="color: var(--el-text-color-secondary); font-size: 13px">暂无进行中的项目</div>
        </el-card>
      </el-col>
      <el-col :span="10">
        <el-card shadow="never" style="height: 100%">
          <div class="section-label">近期截止（按截止时间）</div>
          <template v-if="(wb?.due_soon || []).length">
            <div v-for="d in wb.due_soon" :key="d.task_id" class="due-row">
              <el-tag :type="priorityTagType(d.priority)" size="small">{{ priorityLabel(d.priority) }}</el-tag>
              <span class="due-title">{{ d.title }}</span>
              <span class="due-project">{{ d.project_name }}</span>
              <span class="num due-date">{{ d.planned_end }}</span>
            </div>
          </template>
          <div v-else style="color: var(--el-text-color-secondary); font-size: 13px">暂无待办任务</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 最近动态 -->
    <el-card shadow="never">
      <div class="section-label">最近动态</div>
      <div v-if="(wb?.activity || []).length === 0" style="color: var(--el-text-color-secondary); font-size: 13px">暂无动态</div>
      <div v-for="(a, i) in wb?.activity || []" :key="i" class="ov-activity-item">
        <span style="color: var(--el-color-primary)">{{ a.operator_name }}</span>
        <span>{{ a.task_title }}（{{ a.from_status ? (STATUS_MAP[a.from_status]?.label || a.from_status) : '创建' }} → {{ STATUS_MAP[a.to_status]?.label || a.to_status }}）</span>
        <span class="ov-risk-meta" style="margin-left: auto">{{ timeAgo(a.created_at) }}</span>
      </div>
    </el-card>
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
.wb-greeting {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.wb-greeting__title {
  margin: 0 0 6px;
  font-size: 20px;
  color: var(--text-title);
}
.wb-greeting__date {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
.wb-stat {
  padding: 14px 16px;
  gap: 12px;
}
.wb-stat__num { font-size: 28px; font-weight: bold; font-variant-numeric: tabular-nums; }
.wb-stat__label { font-size: 13px; color: var(--el-text-color-secondary); margin-top: 2px; }
.ring-center {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}
.ring-center__num { font-size: 20px; font-weight: bold; color: var(--text-title); }
.ring-center__label { font-size: 12px; color: var(--el-text-color-secondary); margin-top: 2px; }
.ring-legend-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0;
  font-size: 13px;
}
.ring-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.ring-legend-label { flex: 1; color: var(--el-text-color-regular); }
.ring-legend-value { color: var(--el-text-color-secondary); font-variant-numeric: tabular-nums; }
.top-project-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 0;
  border-bottom: 1px solid var(--el-border-color-lighter);
  cursor: pointer;
  font-size: 13px;
}
.top-project-row:hover .top-project-name { color: var(--el-color-primary); }
.top-project-name {
  flex: 1.2;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--el-text-color-primary);
}
.top-project-progress { display: flex; align-items: center; gap: 6px; }
.due-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
  border-bottom: 1px solid var(--el-border-color-lighter);
  font-size: 13px;
}
.due-title { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--el-text-color-primary); }
.due-project { font-size: 12px; color: var(--el-text-color-placeholder); max-width: 140px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.due-date { color: var(--el-text-color-secondary); }
</style>
