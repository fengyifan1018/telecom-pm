import axios from 'axios'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '../stores/auth'
import router from '../router'

const http = axios.create({
  baseURL: '/api',
  timeout: 10000,
})

http.interceptors.request.use((config) => {
  const auth = useAuthStore()
  if (auth.token) {
    config.headers.Authorization = `Bearer ${auth.token}`
  }
  return config
})

http.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      const auth = useAuthStore()
      auth.logout()
      router.push('/login')
    } else if (!err.config?.skipGlobalError) {
      // 统一错误提示：优先后端 detail，其次区分网络异常 / 通用失败
      const detail = err.response?.data?.detail
      const msg =
        typeof detail === 'string' && detail
          ? detail
          : err.response
            ? '请求失败，请稍后重试'
            : '网络异常，请检查连接后重试'
      ElMessage.error(msg)
    }
    return Promise.reject(err)
  }
)

export default http
