import axios from 'axios'
import type { TripFormData, TripPlanResponse, TripProgressEvent } from '@/types'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 650000, // 约5.8分钟超时
  headers: {
    'Content-Type': 'application/json'
  }
})

// 请求拦截器
apiClient.interceptors.request.use(
  (config) => {
    console.log('发送请求:', config.method?.toUpperCase(), config.url)
    return config
  },
  (error) => {
    console.error('请求错误:', error)
    return Promise.reject(error)
  }
)

// 响应拦截器
apiClient.interceptors.response.use(
  (response) => {
    console.log('收到响应:', response.status, response.config.url)
    return response
  },
  (error) => {
    console.error('响应错误:', error.response?.status, error.message)
    return Promise.reject(error)
  }
)

/**
 * 生成旅行计划
 */
export async function generateTripPlan(formData: TripFormData): Promise<TripPlanResponse> {
  try {
    const response = await apiClient.post<TripPlanResponse>('/api/trip/plan', formData)
    return response.data
  } catch (error: any) {
    console.error('生成旅行计划失败:', error)
    throw new Error(error.response?.data?.detail || error.message || '生成旅行计划失败')
  }
}

/**
 * 流式生成旅行计划，持续接收后端真实 LangGraph 节点进度
 */
export async function streamTripPlan(
  formData: TripFormData,
  onProgress: (event: TripProgressEvent) => void
): Promise<TripPlanResponse> {
  const response = await fetch(`${API_BASE_URL}/api/trip/plan/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'text/event-stream'
    },
    body: JSON.stringify(formData)
  })

  if (!response.ok) {
    const errorText = await response.text()
    throw new Error(errorText || `请求失败: ${response.status}`)
  }

  if (!response.body) {
    throw new Error('浏览器不支持流式响应')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''
  let finalResponse: TripPlanResponse | null = null
  let streamError: Error | null = null

  const processEventBlock = (block: string) => {
    const data = block
      .split('\n')
      .filter((line) => line.startsWith('data:'))
      .map((line) => line.slice(5).trim())
      .join('\n')

    if (!data) {
      return
    }

    const progressEvent = JSON.parse(data) as TripProgressEvent
    onProgress(progressEvent)

    if (progressEvent.event === 'complete') {
      finalResponse = {
        success: true,
        message: progressEvent.message || '旅行计划生成成功',
        data: progressEvent.data
      }
    }

    if (progressEvent.event === 'error') {
      streamError = new Error(progressEvent.message || progressEvent.detail || '生成旅行计划失败')
    }
  }

  while (true) {
    const { done, value } = await reader.read()
    if (done) {
      break
    }

    buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, '\n')
    let delimiterIndex = buffer.indexOf('\n\n')
    while (delimiterIndex !== -1) {
      const eventBlock = buffer.slice(0, delimiterIndex)
      buffer = buffer.slice(delimiterIndex + 2)
      processEventBlock(eventBlock)
      delimiterIndex = buffer.indexOf('\n\n')
    }
  }

  buffer += decoder.decode()
  if (buffer.trim()) {
    processEventBlock(buffer)
  }

  if (streamError) {
    throw streamError
  }

  if (!finalResponse) {
    throw new Error('流式响应结束但未收到旅行计划')
  }

  return finalResponse
}

/**
 * 健康检查
 */
export async function healthCheck(): Promise<any> {
  try {
    const response = await apiClient.get('/health')
    return response.data
  } catch (error: any) {
    console.error('健康检查失败:', error)
    throw new Error(error.message || '健康检查失败')
  }
}

export default apiClient
