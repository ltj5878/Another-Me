import { defineStore } from 'pinia'

import {
  createStyle,
  deleteArticle,
  deleteStyle,
  fetchArticleDetail,
  fetchArticles,
  fetchStyle,
  fetchStyleProfile,
  fetchStyles,
  generateStyleProfile,
  updateStyle,
  updateStyleProfile,
  uploadArticle,
} from '@/api/styles'
import type {
  SourceArticle,
  SourceArticleDetail,
  StyleCategory,
  StyleCreatePayload,
  StyleProfilePayload,
  StyleProfileStatus,
  StyleUpdatePayload,
} from '@/types/api'

interface StylesState {
  styles: StyleCategory[]
  currentStyle: StyleCategory | null
  articles: SourceArticle[]
  currentArticle: SourceArticleDetail | null
  currentProfile: StyleProfileStatus | null
  loading: boolean
  articleLoading: boolean
  articleDetailLoading: boolean
  profileLoading: boolean
  profileGenerating: boolean
}

export const useStylesStore = defineStore('styles', {
  state: (): StylesState => ({
    styles: [],
    currentStyle: null,
    articles: [],
    currentArticle: null,
    currentProfile: null,
    loading: false,
    articleLoading: false,
    articleDetailLoading: false,
    profileLoading: false,
    profileGenerating: false,
  }),
  actions: {
    async loadStyles() {
      this.loading = true
      try {
        this.styles = await fetchStyles()
      } finally {
        this.loading = false
      }
    },
    async addStyle(payload: StyleCreatePayload) {
      const created = await createStyle(payload)
      this.styles = [created, ...this.styles]
      return created
    },
    async editStyle(id: string, payload: StyleUpdatePayload) {
      const updated = await updateStyle(id, payload)
      this.styles = this.styles.map((style) => (style.id === id ? updated : style))
      if (this.currentStyle?.id === id) {
        this.currentStyle = updated
      }
      return updated
    },
    async removeStyle(id: string) {
      await deleteStyle(id)
      this.styles = this.styles.filter((style) => style.id !== id)
    },
    async removeArticle(styleId: string, articleId: string) {
      await deleteArticle(styleId, articleId)
      this.articles = this.articles.filter((article) => article.id !== articleId)
      if (this.currentStyle && this.currentStyle.article_count > 0) {
        this.currentStyle.article_count -= 1
      }
      this.currentProfile = await fetchStyleProfile(styleId)
    },
    async loadStyleDetail(id: string) {
      this.loading = true
      try {
        const [style, articles, profile] = await Promise.all([fetchStyle(id), fetchArticles(id), fetchStyleProfile(id)])
        this.currentStyle = style
        this.articles = articles
        this.currentProfile = profile
        this.currentArticle = null
      } finally {
        this.loading = false
      }
    },
    async uploadStyleArticle(styleId: string, file: File) {
      this.articleLoading = true
      try {
        const article = await uploadArticle(styleId, file)
        this.articles = [article, ...this.articles]
        if (this.currentStyle) {
          this.currentStyle.article_count += 1
        }
        this.currentProfile = await fetchStyleProfile(styleId)
      } finally {
        this.articleLoading = false
      }
    },
    async loadArticleDetail(styleId: string, articleId: string) {
      this.articleDetailLoading = true
      try {
        this.currentArticle = await fetchArticleDetail(styleId, articleId)
        return this.currentArticle
      } finally {
        this.articleDetailLoading = false
      }
    },
    async loadStyleProfile(styleId: string) {
      this.profileLoading = true
      try {
        this.currentProfile = await fetchStyleProfile(styleId)
        return this.currentProfile
      } finally {
        this.profileLoading = false
      }
    },
    async regenerateStyleProfile(styleId: string) {
      this.profileGenerating = true
      try {
        this.currentProfile = await generateStyleProfile(styleId)
        return this.currentProfile
      } finally {
        this.profileGenerating = false
      }
    },
    async saveStyleProfile(styleId: string, payload: StyleProfilePayload) {
      this.profileLoading = true
      try {
        this.currentProfile = await updateStyleProfile(styleId, payload)
        return this.currentProfile
      } finally {
        this.profileLoading = false
      }
    },
  },
})
