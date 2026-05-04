import { apiClient } from '@/api/client'
import type { Generation, GenerationCreatePayload, GenerationDebugRunPayload, GenerationRevisePayload } from '@/types/api'

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
