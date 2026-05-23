import http from './index'

export const listGroups = () => http.get('/groups')

export const createGroup = (data) => http.post('/groups', data)

export const updateGroup = (id, data) => http.put(`/groups/${id}`, data)

export const deleteGroup = (id) => http.delete(`/groups/${id}`)

export const listGroupMembers = (groupId) => http.get(`/groups/${groupId}/members`)

export const addGroupMember = (groupId, userId) =>
  http.post(`/groups/${groupId}/members`, { user_id: userId })

export const removeGroupMember = (groupId, userId) =>
  http.delete(`/groups/${groupId}/members/${userId}`)
