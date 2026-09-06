// 统一的日期/时间/超期格式化工具

/** 取日期部分 YYYY-MM-DD，空值返回 '-' */
export function formatDate(value) {
  return value ? String(value).slice(0, 10) : '-'
}

/** 格式化为 YYYY-MM-DD HH:mm（withSeconds 时到秒），空值返回 '-' */
export function formatDateTime(value, withSeconds = false) {
  if (!value) return '-'
  return String(value).slice(0, withSeconds ? 19 : 16).replace('T', ' ')
}

/** 今天的日期字符串 YYYY-MM-DD（本地时区，用于与后端日期字段比较） */
export function todayStr() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

/** 相对今天已超期的天数（未超期返回 0） */
export function overdueDays(endDate) {
  if (!endDate) return 0
  return Math.max(0, Math.floor((new Date(todayStr()) - new Date(endDate)) / 86400000))
}

/** 相对时间（刚刚 / N 分钟前 / N 小时前 / N 天前，超过 30 天显示日期） */
export function timeAgo(value) {
  if (!value) return '-'
  const then = new Date(String(value).replace(' ', 'T')).getTime()
  const diff = Date.now() - then
  const m = Math.floor(diff / 60000)
  if (m < 1) return '刚刚'
  if (m < 60) return `${m} 分钟前`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h} 小时前`
  const d = Math.floor(h / 24)
  if (d < 30) return `${d} 天前`
  return formatDate(value)
}

/** 截止日临近程度：overdue 已超期 / today 今天到期 / soon 明天到期 / normal */
export function dueTone(endDate, status) {
  if (!endDate || ['done', 'cancelled'].includes(status)) return 'normal'
  const diff = Math.floor((new Date(endDate) - new Date(todayStr())) / 86400000)
  if (diff < 0) return 'overdue'
  if (diff === 0) return 'today'
  if (diff === 1) return 'soon'
  return 'normal'
}

/** 截止日颜色（列表/卡片通用）：超期红、今明橙 */
export function dueColor(endDate, status) {
  const t = dueTone(endDate, status)
  if (t === 'overdue') return 'var(--el-color-danger)'
  if (t === 'today' || t === 'soon') return 'var(--el-color-warning)'
  return ''
}
