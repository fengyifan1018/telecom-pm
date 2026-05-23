import http from './index'

export const listProjects = (params) => http.get('/projects', { params })

export const getProject = (id) => http.get(`/projects/${id}`)

export const createProject = (data) => http.post('/projects', data)

export const updateProject = (id, data) => http.put(`/projects/${id}`, data)

export const initProject = (id) => http.post(`/projects/${id}/init`)

export const listCustomers = () => http.get('/projects/customers')

export const createCustomer = (data) => http.post('/projects/customers', data)

export const updateCustomer = (id, data) => http.put(`/projects/customers/${id}`, data)

export const deleteCustomer = (id) => http.delete(`/projects/customers/${id}`)

export const suspendProject = (id, data) => http.post(`/projects/${id}/suspend`, data)

export const resumeProject = (id, data) => http.post(`/projects/${id}/resume`, data || {})

export const deleteProject = (id) => http.delete(`/projects/${id}`)
