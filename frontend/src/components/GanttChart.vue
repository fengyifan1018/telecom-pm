<script setup>
import { computed } from 'vue'
import { STATUS_MAP } from '../utils/constants'

const props = defineProps({
  tasks: { type: Array, default: () => [] },
})

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
            :style="{ left: t.left + 'px', width: t.width + 'px', background: t.color }"
            :title="`${t.planned_start} ~ ${t.planned_end}`"
          >
            <span class="bar-dates">{{ t.planned_start }} ~ {{ t.planned_end }}</span>
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
  background: #f9f9fb;
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
  background: #fff;
}

.row-label {
  background: #fff;
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
  background: #fff;
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
