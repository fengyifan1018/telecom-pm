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
