import { apiClient } from '@/api/client'
import type { Generation, GenerationCreatePayload, GenerationDebugRunPayload, GenerationRevisePayload } from '@/types/api'

interface GenerationStreamHandlers {
  onStarted?: (payload: { generation_id: string; style_category_id: string; metadata: Record<string, unknown> }) => void
  onProgress?: (message: string) => void
  onDelta?: (content: string) => void
  onCompleted?: (generation: Generation) => void | Promise<void>
  onError?: (message: string) => void
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000'

export async function createGeneration(payload: GenerationCreatePayload): Promise<Generation> {
  const { data } = await apiClient.post<Generation>('/api/v1/generations', payload, {
    timeout: 300000,
  })
  return data
}

export async function fetchGenerations(styleId?: string, limit = 20): Promise<Generation[]> {
  const { data } = await apiClient.get<Generation[]>('/api/v1/generations', {
    params: {
      style_id: styleId || undefined,
      limit,
    },
  })
  return data
}

export async function fetchGeneration(id: string): Promise<Generation> {
  const { data } = await apiClient.get<Generation>(`/api/v1/generations/${id}`)
  return data
}

export async function deleteGeneration(id: string): Promise<void> {
  await apiClient.delete(`/api/v1/generations/${id}`)
}

export async function reviseGeneration(id: string, payload: GenerationRevisePayload): Promise<Generation> {
  const { data } = await apiClient.post<Generation>(`/api/v1/generations/${id}/revise`, payload, {
    timeout: 300000,
  })
  return data
}

export async function debugRunGeneration(payload: GenerationDebugRunPayload): Promise<Generation> {
  const { data } = await apiClient.post<Generation>('/api/v1/generations/debug-run', payload, {
    timeout: 300000,
  })
  return data
}

export async function streamCreateGeneration(payload: GenerationCreatePayload, handlers: GenerationStreamHandlers): Promise<void> {
  await streamGeneration('/api/v1/generations/stream', payload, handlers)
}

export async function streamReviseGeneration(
  id: string,
  payload: GenerationRevisePayload,
  handlers: GenerationStreamHandlers,
): Promise<void> {
  await streamGeneration(`/api/v1/generations/${id}/revise/stream`, payload, handlers)
}

export async function streamDebugRunGeneration(payload: GenerationDebugRunPayload, handlers: GenerationStreamHandlers): Promise<void> {
  await streamGeneration('/api/v1/generations/debug-run/stream', payload, handlers)
}

async function streamGeneration(path: string, payload: unknown, handlers: GenerationStreamHandlers): Promise<void> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
    },
    body: JSON.stringify(payload),
  })

  if (!response.ok) {
    throw new Error(await readFetchError(response))
  }
  if (!response.body) {
    throw new Error('浏览器不支持流式响应')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const events = buffer.split('\n\n')
    buffer = events.pop() || ''
    for (const eventText of events) {
      await handleSseEvent(eventText, handlers)
    }
  }

  buffer += decoder.decode()
  if (buffer.trim()) {
    await handleSseEvent(buffer, handlers)
  }
}

async function handleSseEvent(eventText: string, handlers: GenerationStreamHandlers) {
  const lines = eventText.split('\n')
  const event = lines.find((line) => line.startsWith('event:'))?.slice(6).trim() || 'message'
  const dataLines = lines.filter((line) => line.startsWith('data:')).map((line) => line.slice(5).trimStart())
  const rawData = dataLines.join('\n')
  const payload = rawData ? JSON.parse(rawData) : {}

  if (event === 'started') {
    handlers.onStarted?.(payload)
  } else if (event === 'progress') {
    handlers.onProgress?.(typeof payload.detail === 'string' ? payload.detail : '生成中...')
  } else if (event === 'delta') {
    handlers.onDelta?.(typeof payload.content === 'string' ? payload.content : '')
  } else if (event === 'completed') {
    await handlers.onCompleted?.(payload as Generation)
  } else if (event === 'error') {
    const message = typeof payload.detail === 'string' ? payload.detail : '流式生成失败'
    handlers.onError?.(message)
    throw new Error(message)
  }
}

async function readFetchError(response: Response): Promise<string> {
  try {
    const payload = await response.json()
    if (typeof payload.detail === 'string') return payload.detail
    if (Array.isArray(payload.detail)) {
      return payload.detail.map((item: { msg?: string }) => item.msg || '参数错误').join('；')
    }
  } catch {
    // Fall through to status text.
  }
  return response.statusText || '请求失败'
}
