import axios from 'axios'
import { message } from 'antd'

const request = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
})

// 请求拦截器：自动添加JWT令牌
request.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 响应拦截器：统一错误处理
request.interceptors.response.use(
  (response) => {
    const data = response.data
    if (data.code && data.code !== 200) {
      message.error(data.message || '请求失败')
      return Promise.reject(new Error(data.message))
    }
    return data
  },
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      window.location.href = '/login'
      return
    }
    message.error(error.response?.data?.detail || error.message || '网络错误')
    return Promise.reject(error)
  },
)

export default request
