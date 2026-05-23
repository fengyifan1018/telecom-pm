import { defineStore } from 'pinia'
import { ref } from 'vue'
import { login as apiLogin, getMe } from '../api/auth'
import { getMyPermissions } from '../api/permissions'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('token') || '')
  const user = ref(null)
  const permissions = ref([])

  function hasPermission(key) {
    return permissions.value.includes(key)
  }

  async function login(username, password) {
    const res = await apiLogin(username, password)
    token.value = res.data.access_token
    localStorage.setItem('token', token.value)
    await fetchUser()
  }

  async function fetchUser() {
    const [userRes, permRes] = await Promise.all([getMe(), getMyPermissions()])
    user.value = userRes.data
    permissions.value = permRes.data
  }

  function logout() {
    token.value = ''
    user.value = null
    permissions.value = []
    localStorage.removeItem('token')
  }

  return { token, user, permissions, hasPermission, login, fetchUser, logout }
})
