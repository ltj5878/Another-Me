import axios, { AxiosError } from 'axios'
import { ElMessage } from 'element-plus'

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000',
  timeout: 15000,
})

export function getApiErrorMessage(error: unknown): string {
  if (error instanceof AxiosError) {
    const detail = error.response?.data?.detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) return detail.map((item) => item.msg).join('；')
    if (error.code === 'ERR_NETWORK') return '无法连接后端服务，请确认 API 已启动'
    if (error.code === 'ECONNABORTED') return '请求超时，请稍后重试'
    return error.message
  }
  if (error instanceof Error) return error.message
  return '请求失败'
}

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    ElMessage.error(getApiErrorMessage(error))
    return Promise.reject(error)
  },
)
