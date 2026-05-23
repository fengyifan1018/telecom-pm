import http from './index'

export const listDeliverables = (projectId, phase) =>
  http.get(`/projects/${projectId}/deliverables`, { params: phase ? { phase } : {} })

export const uploadDeliverable = (projectId, formData) =>
  http.post(`/projects/${projectId}/deliverables`, formData)

export const downloadDeliverableUrl = (projectId, deliverableId) =>
  `/api/projects/${projectId}/deliverables/${deliverableId}/download`

export const deleteDeliverable = (projectId, deliverableId) =>
  http.delete(`/projects/${projectId}/deliverables/${deliverableId}`)
