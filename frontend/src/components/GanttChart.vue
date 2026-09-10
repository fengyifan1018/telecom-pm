<script setup>
import { computed, reactive } from 'vue'
import { STATUS_MAP } from '../utils/constants'
import { updateTask } from '../api/tasks'
import { useAuthStore } from '../stores/auth'
import { ElMessage } from 'element-plus'

const props = defineProps({
  tasks: { type: Array, default: () => [] },
})
const emit = defineEmits(['refresh'])
const auth = useAuthStore()

// 拖拽改排期权限：PM/管理员或负责人本人；done/cancelled 不可拖
function canDrag(t) {
  if (!t.hasBar || ['done', 'cancelled'].includes(t.status)) return false
  return ['pm', 'admin'].includes(auth.user?.role) || t.assignee_id === auth.user?.id
}

const PX_PER_DAY = 28

const STATUS_COLORS = {
  pending:   'var(--el-border-color)',
  active:    'var(--el-color-primary)',
  review:    'var(--el-color-warning)',
  done:      'var(--el-color-success)',
  paused:    'var(--el-text-color-secondary)',
  blocked:   'var(--el-color-danger)',
  rework:    'var(--el-color-warning)',
  cancelled: 'var(--el-text-color-placeholder)',
}

// Parse "YYYY-MM-DD" as local midnight — avoids UTC-offset shifting
function parseDate(str) {
  const [y, m, d] = str.split('-').map(Number)
  return new Date(y, m - 1, d)
}

function daysBetween(a, b) {
  return Math.round((b.getTime() - a.getTime()) / 86400000)
}

const chartData = computed(() => {
  const withDates = props.tasks.filter(t => t.planned_start && t.planned_end)
  if (withDates.length === 0) return null

  const starts = withDates.map(t => parseDate(t.planned_start).getTime())
  const ends   = withDates.map(t => parseDate(t.planned_end).getTime())

  const rangeStart = parseDate(withDates[starts.indexOf(Math.min(...starts))].planned_start)
  const rangeEnd   = parseDate(withDates[ends.indexOf(Math.max(...ends))].planned_end)

  const totalDays  = daysBetween(rangeStart, rangeEnd) + 1
  const totalWidth = totalDays * PX_PER_DAY

  // One entry per day
  const days = Array.from({ length: totalDays }, (_, i) => {
    const d = new Date(rangeStart)
    d.setDate(d.getDate() + i)
    const dow = d.getDay()
    return {
      i,
      num:       d.getDate(),
      year:      d.getFullYear(),
      month:     d.getMonth(),
      isWeekend: dow === 0 || dow === 6,
      left:      i * PX_PER_DAY,
    }
  })

  // Group days into months for the top header row
  const monthGroups = []
  let cur = null
  for (const day of days) {
    const key = `${day.year}-${day.month}`
    if (!cur || cur.key !== key) {
      cur = {
        key,
        label: `${day.year}年${day.month + 1}月`,
        left:  day.left,
        width: PX_PER_DAY,
      }
      monthGroups.push(cur)
    } else {
      cur.width += PX_PER_DAY
    }
  }

  // Task bar data for every task
  const rows = props.tasks.map(t => {
    if (!t.planned_start || !t.planned_end) {
      return { ...t, hasBar: false }
    }
    const s      = parseDate(t.planned_start)
    const e      = parseDate(t.planned_end)
    const offset = daysBetween(rangeStart, s)
    const dur    = Math.max(daysBetween(s, e) + 1, 1)
    return {
      ...t,
      hasBar: true,
      left:   offset * PX_PER_DAY,
      width:  dur * PX_PER_DAY,
      color:  STATUS_COLORS[t.status] || 'var(--el-border-color)',
    }
  })

  // Today marker
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const todayOff  = daysBetween(rangeStart, today)
  const todayLeft = todayOff >= 0 && todayOff < totalDays
    ? todayOff * PX_PER_DAY
    : null

  return { rows, totalWidth, days, monthGroups, todayLeft }
})

// ── 拖拽调整排期（move 整体平移 / resize-start/end 两端缩放，按天吸附） ──
const drag = reactive({ taskId: null, mode: null, startX: 0, origLeft: 0, origWidth: 0, dx: 0 })
const dragDays = computed(() => Math.round(drag.dx / PX_PER_DAY))

function addDays(dt, n) {
  const x = new Date(dt)
  x.setDate(x.getDate() + n)
  return x
}
function fmtDate(dt) {
  return `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, '0')}-${String(dt.getDate()).padStart(2, '0')}`
}

function barStyle(t) {
  if (drag.taskId !== t.id) return { left: t.left + 'px', width: t.width + 'px', background: t.color }
  let left = drag.origLeft
  let width = drag.origWidth
  const d = dragDays.value
  if (drag.mode === 'move') left += d * PX_PER_DAY
  else if (drag.mode === 'resize-end') width = Math.max(drag.origWidth + d * PX_PER_DAY, PX_PER_DAY)
  else if (drag.mode === 'resize-start') {
    width = Math.max(drag.origWidth - d * PX_PER_DAY, PX_PER_DAY)
    left += drag.origWidth - width
  }
  return { left: left + 'px', width: width + 'px', background: t.color }
}

function barTitle(t) {
  if (drag.taskId !== t.id) return `${t.planned_start} ~ ${t.planned_end}`
  const s = parseDate(t.planned_start)
  const e = parseDate(t.planned_end)
  const d = dragDays.value
  let ns = s, ne = e
  if (drag.mode === 'move') { ns = addDays(s, d); ne = addDays(e, d) }
  else if (drag.mode === 'resize-end') ne = addDays(e, d)
  else if (drag.mode === 'resize-start') ns = addDays(s, d)
  if (ns > ne) [ns, ne] = [ne, ns]
  return `${fmtDate(ns)} ~ ${fmtDate(ne)}（松开保存）`
}

function onBarDown(e, t, mode) {
  if (!canDrag(t)) return
  e.preventDefault()
  drag.taskId = t.id
  drag.mode = mode
  drag.startX = e.clientX
  drag.origLeft = t.left
  drag.origWidth = t.width
  drag.dx = 0
  window.addEventListener('mousemove', onDragMove)
  window.addEventListener('mouseup', onDragUp)
}
function onDragMove(e) {
  drag.dx = e.clientX - drag.startX
}
async function onDragUp() {
  window.removeEventListener('mousemove', onDragMove)
  window.removeEventListener('mouseup', onDragUp)
  const t = props.tasks.find(x => x.id === drag.taskId)
  const mode = drag.mode
  const d = dragDays.value
  drag.taskId = null
  drag.dx = 0
  if (!t || !d) return
  const s = parseDate(t.planned_start)
  const e = parseDate(t.planned_end)
  let ns = s, ne = e
  if (mode === 'move') { ns = addDays(s, d); ne = addDays(e, d) }
  else if (mode === 'resize-end') ne = addDays(e, d)
  else if (mode === 'resize-start') ns = addDays(s, d)
  if (ne < ns) ne = ns
  try {
    const res = await updateTask(t.id, { planned_start: fmtDate(ns), planned_end: fmtDate(ne) })
    const n = res.data?.rescheduled || 0
    ElMessage.success(n > 0 ? `排期已更新，联动顺延 ${n} 个后续任务` : '排期已更新')
    emit('refresh')
  } catch {
    // 错误提示由全局拦截器统一处理；组件由父级刷新还原
    emit('refresh')
  }
}
</script>

<template>
  <div v-if="chartData" class="gantt-outer">
    <div class="gantt-scroll">

      <!-- ── Header ── -->
      <div class="gantt-head-wrap">
        <!-- sticky label cell (spans both header rows) -->
        <div class="g-label sticky-col head-label">任务</div>

        <!-- Two-row timeline header -->
        <div class="g-head-timeline" :style="{ width: chartData.totalWidth + 'px' }">

          <!-- Row 1: month groups -->
          <div class="month-row">
            <div
              v-for="mg in chartData.monthGroups"
              :key="mg.key"
              class="month-cell"
              :style="{ left: mg.left + 'px', width: mg.width + 'px' }"
            >{{ mg.label }}</div>
          </div>

          <!-- Row 2: individual days -->
          <div class="day-row">
            <div
              v-for="d in chartData.days"
              :key="d.i"
              class="day-cell"
              :class="{
                weekend: d.isWeekend,
                'today-col': chartData.todayLeft === d.left,
              }"
              :style="{ left: d.left + 'px', width: PX_PER_DAY + 'px' }"
            >{{ d.num }}</div>
          </div>

          <!-- Today marker line in header -->
          <div
            v-if="chartData.todayLeft !== null"
            class="today-line"
            :style="{ left: chartData.todayLeft + 'px' }"
          />
        </div>
      </div>

      <!-- ── Task rows ── -->
      <div
        v-for="t in chartData.rows"
        :key="t.id"
        class="gantt-row"
      >
        <div class="g-label sticky-col row-label" :title="t.title">
          <span class="label-text">{{ t.title }}</span>
          <el-tag
            :type="STATUS_MAP[t.status]?.type"
            size="small"
            style="flex-shrink:0; margin-left:4px"
          >{{ STATUS_MAP[t.status]?.label }}</el-tag>
        </div>

        <div class="g-timeline" :style="{ width: chartData.totalWidth + 'px' }">
          <!-- Weekend column shading -->
          <template v-for="d in chartData.days" :key="d.i">
            <div
              v-if="d.isWeekend"
              class="weekend-shade"
              :style="{ left: d.left + 'px', width: PX_PER_DAY + 'px' }"
            />
          </template>

          <!-- Today line -->
          <div
            v-if="chartData.todayLeft !== null"
            class="today-line row-today"
            :style="{ left: chartData.todayLeft + 'px' }"
          />

          <!-- Task bar -->
          <div
            v-if="t.hasBar"
            class="gantt-bar"
            :class="{ draggable: canDrag(t), dragging: drag.taskId === t.id }"
            :style="barStyle(t)"
            :title="barTitle(t)"
            @mousedown="onBarDown($event, t, 'move')"
          >
            <span v-if="canDrag(t)" class="bar-handle is-left" @mousedown.stop="onBarDown($event, t, 'resize-start')" />
            <span class="bar-dates">{{ t.planned_start }} ~ {{ t.planned_end }}</span>
            <span v-if="canDrag(t)" class="bar-handle is-right" @mousedown.stop="onBarDown($event, t, 'resize-end')" />
          </div>

          <span v-else class="no-date">未设置排期</span>
        </div>
      </div>

    </div>
  </div>

  <div v-else style="text-align:center; color:var(--el-text-color-secondary); padding:40px 0">
    暂无排期数据（需在任务抽屉中为任务设置计划开始/结束日期）
  </div>
</template>

<style scoped>
.gantt-outer {
  border: 1px solid var(--el-border-color);
  border-radius: 4px;
  overflow: hidden;
  font-size: 12px;
}

.gantt-scroll {
  overflow-x: auto;
}

/* ── Header ── */
.gantt-head-wrap {
  display: flex;
  align-items: stretch;
  background: var(--el-fill-color-light);
  border-bottom: 2px solid var(--el-border-color);
  position: sticky;
  top: 0;
  z-index: 10;
}

.head-label {
  font-weight: bold;
  color: var(--el-text-color-regular);
  background: var(--el-fill-color-light);
  /* height = month row (22px) + day row (24px) */
  height: 46px;
}

.g-head-timeline {
  position: relative;
  height: 46px;
  flex-shrink: 0;
}

.month-row {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 22px;
  border-bottom: 1px solid var(--el-border-color);
}

.month-cell {
  position: absolute;
  height: 22px;
  display: flex;
  align-items: center;
  padding: 0 6px;
  font-size: 11px;
  font-weight: bold;
  color: var(--el-text-color-primary);
  border-right: 1px solid var(--el-border-color);
  box-sizing: border-box;
  white-space: nowrap;
  overflow: hidden;
}

.day-row {
  position: absolute;
  top: 22px;
  left: 0;
  right: 0;
  height: 24px;
}

.day-cell {
  position: absolute;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-right: 1px solid #ebeef5;
  box-sizing: border-box;
  color: var(--el-text-color-regular);
  font-size: 11px;
}

.day-cell.weekend {
  color: var(--el-color-warning);
  background: rgba(230, 162, 60, 0.08);
}

.day-cell.today-col {
  color: var(--el-color-danger);
  font-weight: bold;
  background: rgba(245, 108, 108, 0.1);
}

/* ── Task rows ── */
.gantt-row {
  display: flex;
  align-items: stretch;
  min-height: 34px;
  border-bottom: 1px solid #f0f0f0;
}

.gantt-row:last-child {
  border-bottom: none;
}

.gantt-row:hover .row-label,
.gantt-row:hover .g-timeline {
  background: var(--el-fill-color-lighter);
}

/* ── Label column ── */
.g-label {
  width: 220px;
  min-width: 220px;
  padding: 4px 8px;
  display: flex;
  align-items: center;
  border-right: 1px solid var(--el-border-color);
  overflow: hidden;
}

.sticky-col {
  position: sticky;
  left: 0;
  z-index: 5;
  background: var(--el-bg-color);
}

.row-label {
  background: var(--el-bg-color);
}

.label-text {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ── Timeline area ── */
.g-timeline {
  position: relative;
  height: 34px;
  flex-shrink: 0;
  background: var(--el-bg-color);
  /* subtle day grid via repeating gradient (28px = PX_PER_DAY) */
  background-image: repeating-linear-gradient(
    to right,
    transparent 0px,
    transparent 27px,
    #f0f0f0 27px,
    #f0f0f0 28px
  );
}

.weekend-shade {
  position: absolute;
  top: 0;
  bottom: 0;
  background: rgba(230, 162, 60, 0.07);
  pointer-events: none;
}

/* ── Today line ── */
.today-line {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 2px;
  background: var(--el-color-danger);
  z-index: 2;
  pointer-events: none;
}

.row-today {
  opacity: 0.4;
}

/* ── Task bar ── */
.gantt-bar {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  height: 20px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  overflow: hidden;
  min-width: 4px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.15);
  cursor: default;
  z-index: 1;
}

.gantt-bar.draggable { cursor: grab; }
.gantt-bar.dragging { cursor: grabbing; opacity: 0.85; z-index: 3; box-shadow: 0 2px 8px rgba(0,0,0,0.25); }
.bar-handle {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 8px;
  cursor: ew-resize;
}
.bar-handle.is-left { left: 0; border-radius: 10px 0 0 10px; }
.bar-handle.is-right { right: 0; border-radius: 0 10px 10px 0; }
.bar-handle:hover { background: rgba(255, 255, 255, 0.25); }
.bar-dates {
  padding: 0 8px;
  font-size: 10px;
  color: rgba(255, 255, 255, 0.92);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.no-date {
  position: absolute;
  top: 50%;
  left: 10px;
  transform: translateY(-50%);
  color: var(--el-text-color-placeholder);
  font-size: 12px;
}
</style>
