import http from './index'

export const listProjects = (params) => http.get('/projects', { params })

export const getProject = (id) => http.get(`/projects/${id}`)
export const getProjectActivity = (id, limit = 8) => http.get(`/projects/${id}/activity`, { params: { limit } })
export const getProjectOpenEscalations = (id) => http.get(`/projects/${id}/open-escalations`)

export const createProject = (data) => http.post('/projects', data)

export const updateProject = (id, data) => http.put(`/projects/${id}`, data)

export const initProject = (id) => http.post(`/projects/${id}/init`)
export const submitInitiation = (id) => http.post(`/projects/${id}/submit-initiation`)
export const initApproval = (id, data) => http.post(`/projects/${id}/init-approval`, data)

export const listCustomers = () => http.get('/projects/customers')

export const createCustomer = (data) => http.post('/projects/customers', data)

export const updateCustomer = (id, data) => http.put(`/projects/customers/${id}`, data)

export const deleteCustomer = (id) => http.delete(`/projects/customers/${id}`)

export const suspendProject = (id, data) => http.post(`/projects/${id}/suspend`, data)

export const resumeProject = (id, data) => http.post(`/projects/${id}/resume`, data || {})

export const deleteProject = (id) => http.delete(`/projects/${id}`)
