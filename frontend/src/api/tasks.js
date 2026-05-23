import http from './index'

export const listTasks = (params) => http.get('/tasks', { params })

export const getTask = (id) => http.get(`/tasks/${id}`)

export const updateTask = (id, data) => http.put(`/tasks/${id}`, data)

export const assignTask = (id, data) => http.put(`/tasks/${id}/assign`, data)

export const startTask = (id) => http.put(`/tasks/${id}/start`, {})

export const submitTask = (id, remark) => http.put(`/tasks/${id}/submit`, { remark })

export const approveTask = (id, remark) => http.put(`/tasks/${id}/approve`, { remark })

export const rejectTask = (id, remark) => http.put(`/tasks/${id}/reject`, { remark })

export const getComments = (id) => http.get(`/tasks/${id}/comments`)

export const addComment = (id, content) => http.post(`/tasks/${id}/comments`, { content })

export const getTransitions = (id) => http.get(`/tasks/${id}/transitions`)

export const getDashboard = () => http.get('/dashboard/my-workbench')

export const getOverview = () => http.get('/dashboard/overview')

export const getPhaseStats = () => http.get('/dashboard/phase-stats')

export const getUserWorkload = () => http.get('/dashboard/user-workload')

export const listTemplates = () => http.get('/templates')

export const getTemplate = (id) => http.get(`/templates/${id}`)

export const listUsers = (params) => http.get('/users', { params })

export const getNotifications = (params) => http.get('/notifications', { params })

export const getUnreadCount = () => http.get('/notifications/unread-count')

export const markNotificationRead = (id) => http.put(`/notifications/${id}/read`)

export const markAllRead = () => http.put('/notifications/read-all')

export const listAttachments = (taskId) => http.get(`/tasks/${taskId}/attachments`)

export const uploadAttachment = (taskId, file) => {
  const formData = new FormData()
  formData.append('file', file)
  return http.post(`/tasks/${taskId}/attachments`, formData)
}

export const deleteAttachment = (taskId, attachmentId) =>
  http.delete(`/tasks/${taskId}/attachments/${attachmentId}`)

export const getAttachmentDownloadUrl = (taskId, attachmentId) =>
  `/api/tasks/${taskId}/attachments/${attachmentId}/download`

export const listEscalations = (taskId) => http.get(`/tasks/${taskId}/escalations`)

export const createEscalation = (taskId, data) => http.post(`/tasks/${taskId}/escalations`, data)

export const resolveEscalation = (taskId, escalationId, data) =>
  http.put(`/tasks/${taskId}/escalations/${escalationId}/resolve`, data)
