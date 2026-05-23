import http from './index'

export const login = (username, password) =>
  http.post('/auth/login', { username, password })

export const getMe = () => http.get('/auth/me')
