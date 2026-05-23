import http from './index'

export const listCRs = (projectId) => http.get(`/projects/${projectId}/change-requests`)

export const createCR = (projectId, data) => http.post(`/projects/${projectId}/change-requests`, data)

export const approveCR = (projectId, crId) => http.put(`/projects/${projectId}/change-requests/${crId}/approve`)

export const rejectCR = (projectId, crId, data) => http.put(`/projects/${projectId}/change-requests/${crId}/reject`, data)
