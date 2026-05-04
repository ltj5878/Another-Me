import { apiClient } from '@/api/client'
import type {
  SourceArticle,
  SourceArticleDetail,
  StyleCategory,
  StyleCreatePayload,
  StyleProfilePayload,
  StyleProfileStatus,
  StyleUpdatePayload,
} from '@/types/api'

export async function fetchStyles(): Promise<StyleCategory[]> {
  const { data } = await apiClient.get<StyleCategory[]>('/api/v1/styles')
  return data
}

export async function createStyle(payload: StyleCreatePayload): Promise<StyleCategory> {
  const { data } = await apiClient.post<StyleCategory>('/api/v1/styles', payload)
  return data
}

export async function fetchStyle(id: string): Promise<StyleCategory> {
  const { data } = await apiClient.get<StyleCategory>(`/api/v1/styles/${id}`)
  return data
}

export async function updateStyle(id: string, payload: StyleUpdatePayload): Promise<StyleCategory> {
  const { data } = await apiClient.patch<StyleCategory>(`/api/v1/styles/${id}`, payload)
  return data
}

export async function deleteStyle(id: string): Promise<void> {
  await apiClient.delete(`/api/v1/styles/${id}`)
}

export async function fetchArticles(styleId: string): Promise<SourceArticle[]> {
  const { data } = await apiClient.get<SourceArticle[]>(`/api/v1/styles/${styleId}/articles`)
  return data
}

export async function fetchArticleDetail(styleId: string, articleId: string): Promise<SourceArticleDetail> {
  const { data } = await apiClient.get<SourceArticleDetail>(`/api/v1/styles/${styleId}/articles/${articleId}`)
  return data
}

export async function deleteArticle(styleId: string, articleId: string): Promise<void> {
  await apiClient.delete(`/api/v1/styles/${styleId}/articles/${articleId}`)
}

export async function uploadArticle(styleId: string, file: File): Promise<SourceArticle> {
  const formData = new FormData()
  formData.append('file', file)
  const { data } = await apiClient.post<SourceArticle>(`/api/v1/styles/${styleId}/articles/upload`, formData)
  return data
}

export async function fetchStyleProfile(styleId: string): Promise<StyleProfileStatus> {
  const { data } = await apiClient.get<StyleProfileStatus>(`/api/v1/styles/${styleId}/profile`)
  return data
}

export async function generateStyleProfile(styleId: string): Promise<StyleProfileStatus> {
  const { data } = await apiClient.post<StyleProfileStatus>(`/api/v1/styles/${styleId}/profile/generate`, null, {
    timeout: 180000,
  })
  return data
}

export async function updateStyleProfile(styleId: string, payload: StyleProfilePayload): Promise<StyleProfileStatus> {
  const { data } = await apiClient.patch<StyleProfileStatus>(`/api/v1/styles/${styleId}/profile`, payload)
  return data
}
