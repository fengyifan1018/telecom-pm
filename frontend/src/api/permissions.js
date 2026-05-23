import http from './index'

export const getPermissions = () => http.get('/permissions')

export const updatePermission = (key, roles) => http.put(`/permissions/${key}`, { roles })

export const resetPermissions = () => http.post('/permissions/reset')

export const getMyPermissions = () => http.get('/permissions/me')
