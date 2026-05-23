import http from './index'

export const getAuditLogs = (params) => http.get('/audit', { params })
