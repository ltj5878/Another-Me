<template>
  <section class="page">
    <header class="page-header">
      <div>
        <p class="eyebrow">Style Detail</p>
        <h1>{{ store.currentStyle?.name || '风格详情' }}</h1>
        <p class="page-copy">{{ store.currentStyle?.description || '上传这个风格下的源文章，阶段 2 会基于它们生成风格资料。' }}</p>
      </div>
      <div class="header-actions">
        <el-button type="primary" plain :icon="EditPen" :disabled="!store.currentStyle" @click="dialogOpen = true">编辑风格</el-button>
        <el-button :icon="Back" @click="$router.push('/styles')">返回风格库</el-button>
      </div>
    </header>

    <div class="detail-grid">
      <section class="panel">
        <div class="panel-header">
          <div>
            <h2>上传文章</h2>
            <p>当前支持 UTF-8 编码的 .txt / .md 文件，以及 .docx 文档。</p>
          </div>
        </div>
        <el-upload
          ref="uploadRef"
          drag
          :auto-upload="false"
          :show-file-list="false"
          accept=".txt,.md,.docx"
          :on-change="handleFileChange"
        >
          <el-icon class="upload-icon"><UploadFilled /></el-icon>
          <div class="el-upload__text">拖拽文件到这里，或点击选择</div>
          <template #tip>
            <div class="el-upload__tip">文件内容会提取、清洗并写入数据库，原文件本体不会保存。</div>
          </template>
        </el-upload>
        <div v-if="selectedFile" class="selected-file">已选择：{{ selectedFile.name }}</div>
        <el-button class="upload-button" type="primary" :loading="store.articleLoading" :disabled="!selectedFile" @click="handleUpload">
          上传到当前风格
        </el-button>
      </section>

      <section class="panel">
        <div class="metric">
          <span>已上传文章</span>
          <strong>{{ store.currentStyle?.article_count ?? store.articles.length }}</strong>
        </div>
        <div class="metric">
          <span>处理状态</span>
          <strong>{{ hasProcessingArticles ? '后台处理中' : '空闲' }}</strong>
        </div>
        <div class="metric">
          <span>写作类型</span>
          <strong>{{ store.currentStyle?.writing_type_hint || '混合风格' }}</strong>
        </div>
      </section>
    </div>

    <section class="panel profile-panel" v-loading="store.profileLoading">
      <div class="panel-header">
        <div>
          <h2>风格画像</h2>
          <p>画像会总结这个风格的句式、结构、修辞和模仿指令，写文章页会用它组装 Prompt 预览。</p>
        </div>
        <div class="profile-actions">
          <el-button :icon="EditPen" :disabled="!store.currentProfile" @click="openProfileDialog">编辑画像</el-button>
          <el-button
            type="primary"
            :loading="store.profileGenerating || isProfileGenerating"
            :disabled="!store.currentProfile?.can_generate || isProfileGenerating"
            @click="handleGenerateProfile"
          >
            {{ isProfileGenerating ? '分析中' : '重新分析风格' }}
          </el-button>
        </div>
      </div>

      <div v-if="store.currentProfile" class="profile-status">
        <el-tag effect="plain">完成文章 {{ store.currentProfile.completed_article_count }} / {{ store.currentProfile.minimum_required_articles }}</el-tag>
        <el-tag v-if="store.currentProfile.profile" type="success" effect="plain">v{{ store.currentProfile.profile.version }}</el-tag>
        <el-tag v-if="store.currentProfile.is_stale" type="warning" effect="plain">画像可能已过期</el-tag>
        <el-tag v-if="isProfileGenerating" type="warning" effect="plain">画像分析中</el-tag>
        <el-tag v-else-if="profileGenerationStatus === 'failed'" type="danger" effect="plain">画像分析失败</el-tag>
        <span v-if="store.currentProfile.profile">更新于 {{ formatDate(store.currentProfile.profile.updated_at) }}</span>
        <span v-else>还没有生成风格画像</span>
      </div>

      <el-alert
        v-if="profileGenerationStatus === 'failed' && profileGenerationError"
        class="profile-alert"
        type="error"
        :closable="false"
        :title="profileGenerationError"
      />

      <el-alert
        v-if="store.currentProfile && !store.currentProfile.can_generate"
        class="profile-alert"
        type="info"
        :closable="false"
        :title="`至少需要 ${store.currentProfile.minimum_required_articles} 篇 completed 文章才能生成画像`"
      />

      <template v-if="store.currentProfile?.profile">
        <el-collapse v-model="profileCollapseActive" class="profile-collapse">
          <el-collapse-item name="base">
            <template #title>
              <span class="collapse-heading">
                <span class="collapse-heading-main">
                  <span class="collapse-title">风格画像</span>
                  <span class="collapse-subtitle">总体风格、句式、结构、修辞和生成指令</span>
                </span>
                <span class="collapse-kicker">基础画像</span>
              </span>
            </template>
            <div class="profile-grid">
              <article v-for="field in baseProfileFields" :key="field.key" class="profile-field" :class="{ 'profile-field-wide': field.wide }">
                <h3>{{ field.label }}</h3>
                <p>{{ formatProfileValue(store.currentProfile.profile[field.key]) }}</p>
              </article>
            </div>
          </el-collapse-item>

          <el-collapse-item name="deep">
            <template #title>
              <span class="collapse-heading">
                <span class="collapse-heading-main">
                  <span class="collapse-title">深度分析</span>
                  <span class="collapse-subtitle">句法、标点、词汇和结构会作为写文章时的软约束</span>
                </span>
                <span class="collapse-kicker">Prompt 约束</span>
              </span>
            </template>
            <div class="profile-grid">
              <article v-for="field in deepProfileFields" :key="field.key" class="profile-field" :class="{ 'profile-field-wide': field.wide }">
                <h3>{{ field.label }}</h3>
                <p>{{ formatProfileValue(store.currentProfile.profile[field.key]) }}</p>
              </article>
            </div>
          </el-collapse-item>

          <el-collapse-item v-if="hasMetrics" name="metrics">
            <template #title>
              <span class="collapse-heading">
                <span class="collapse-heading-main">
                  <span class="collapse-title">量化指标</span>
                  <span class="collapse-subtitle">句长、标点频率、段落长度、高频词和结构标签</span>
                </span>
                <span class="collapse-kicker">统计结果</span>
              </span>
            </template>
            <div class="metrics-grid">
              <article class="metric-card">
                <h4>句法指纹</h4>
                <p>平均句长：{{ metricValue('syntax', 'avg_sentence_length') }}</p>
                <p>中位句长：{{ metricValue('syntax', 'median_sentence_length') }}</p>
                <p>短句比例：{{ metricRatio('syntax', 'short_sentence_ratio') }}</p>
                <p>长句比例：{{ metricRatio('syntax', 'long_sentence_ratio') }}</p>
              </article>
              <article class="metric-card">
                <h4>标点习惯</h4>
                <p>主要标点：{{ dominantMarks }}</p>
                <p>逗号/千字：{{ punctuationPerThousand('comma') }}</p>
                <p>问号/千字：{{ punctuationPerThousand('question') }}</p>
                <p>破折号/千字：{{ punctuationPerThousand('dash') }}</p>
              </article>
              <article class="metric-card">
                <h4>段落结构</h4>
                <p>平均段长：{{ metricValue('paragraphs', 'avg_paragraph_length') }}</p>
                <p>短段比例：{{ metricRatio('paragraphs', 'short_paragraph_ratio') }}</p>
                <p>长段比例：{{ metricRatio('paragraphs', 'long_paragraph_ratio') }}</p>
                <p>开头段均长：{{ metricValue('paragraphs', 'opening_avg_length') }}</p>
              </article>
              <article class="metric-card metric-card-wide">
                <h4>词汇偏好</h4>
                <p>高频词：{{ topMetricItems('top_words') }}</p>
                <p>连接词：{{ topMetricItems('connectors') }}</p>
                <p>个人化短语：{{ topMetricItems('private_phrases') }}</p>
                <p>结构标签：{{ structureTags }}</p>
              </article>
            </div>
          </el-collapse-item>
        </el-collapse>
      </template>
      <el-empty v-else description="上传至少 3 篇文章后，可以重新分析并生成风格画像" />
    </section>

    <section class="panel table-panel">
      <div class="panel-header">
        <div>
          <h2>源文章</h2>
          <p>这些文章后续会进入分段、embedding 和风格画像流程。</p>
        </div>
      </div>
      <el-table
        v-if="store.loading || store.articles.length > 0"
        v-loading="store.loading"
        :data="store.articles"
        row-key="id"
        class="clickable-table"
        @row-click="handleArticleClick"
      >
        <el-table-column prop="title" label="标题" min-width="220" />
        <el-table-column prop="original_filename" label="文件名" min-width="220" />
        <el-table-column prop="source_type" label="类型" width="110">
          <template #default="scope">{{ formatSourceType(scope?.row?.source_type) }}</template>
        </el-table-column>
        <el-table-column prop="word_count" label="字数" width="100" />
        <el-table-column prop="status" label="状态" width="120">
          <template #default="scope">
            <el-tag v-if="scope?.row" :type="statusTagType(scope.row.status)" effect="plain">{{ scope.row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="上传时间" width="190">
          <template #default="scope">{{ scope?.row ? formatDate(scope.row.created_at) : '' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="90" align="center">
          <template #default="scope">
            <el-button v-if="scope?.row" type="danger" plain size="small" :icon="Delete" @click.stop="handleDeleteArticle(scope.row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-else description="还没有上传文章" />
    </section>

    <StyleFormDialog
      v-model="dialogOpen"
      mode="edit"
      :style="store.currentStyle"
      :saving="submitting"
      @submit="handleUpdateStyle"
    />

    <el-dialog v-model="articleDialogOpen" title="文章详情" width="820px" class="article-dialog">
      <div v-loading="store.articleDetailLoading">
        <template v-if="store.currentArticle">
          <div class="article-meta">
            <h2>{{ store.currentArticle.title }}</h2>
            <div>
              <el-tag effect="plain">{{ formatSourceType(store.currentArticle.source_type) }}</el-tag>
              <el-tag :type="statusTagType(store.currentArticle.status)" effect="plain">{{ store.currentArticle.status }}</el-tag>
              <span>{{ store.currentArticle.word_count }} 字</span>
              <span>{{ store.currentArticle.chunks.length }} 块</span>
            </div>
          </div>
          <el-tabs v-model="activeArticleTab">
            <el-tab-pane label="清洗后文本" name="cleaned">
              <pre class="article-text">{{ store.currentArticle.cleaned_text }}</pre>
            </el-tab-pane>
            <el-tab-pane label="原文" name="raw">
              <pre class="article-text">{{ store.currentArticle.raw_text }}</pre>
            </el-tab-pane>
            <el-tab-pane :label="`分块情况 (${store.currentArticle.chunks.length})`" name="chunks">
              <div v-if="store.currentArticle.chunks.length > 0" class="chunk-list">
                <article v-for="chunk in store.currentArticle.chunks" :key="chunk.id" class="chunk-item">
                  <header>
                    <strong>#{{ chunk.chunk_index + 1 }}</strong>
                    <span>{{ chunk.content.length }} 字符</span>
                    <span>{{ chunk.token_count }} tokens</span>
                    <el-tag effect="plain" size="small">{{ formatChunkPosition(chunk.metadata.position) }}</el-tag>
                    <span>{{ chunk.metadata.paragraph_count ?? 0 }} 段</span>
                  </header>
                  <pre class="chunk-content">{{ chunk.content }}</pre>
                </article>
              </div>
              <el-empty v-else description="还没有分块数据" />
            </el-tab-pane>
          </el-tabs>
        </template>
      </div>
    </el-dialog>

    <el-dialog v-model="profileDialogOpen" title="编辑风格画像" width="860px" class="profile-dialog">
      <el-form label-position="top" class="profile-form">
        <el-form-item v-for="field in profileFields" :key="field.key" :label="field.label">
          <el-input v-model="profileForm[field.key]" type="textarea" :rows="field.rows || 3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="profileDialogOpen = false">取消</el-button>
        <el-button type="primary" :loading="store.profileLoading" @click="handleSaveProfile">保存画像</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup lang="ts">
import { Back, Delete, EditPen, UploadFilled } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox, type UploadFile, type UploadInstance } from 'element-plus'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import StyleFormDialog from '@/components/StyleFormDialog.vue'
import { useStylesStore } from '@/stores/styles'
import type { SourceArticle, StyleCreatePayload, StyleProfilePayload } from '@/types/api'

const props = defineProps<{ id: string }>()
const store = useStylesStore()
const selectedFile = ref<File | null>(null)
const uploadRef = ref<UploadInstance>()
const dialogOpen = ref(false)
const articleDialogOpen = ref(false)
const profileDialogOpen = ref(false)
const submitting = ref(false)
const activeArticleTab = ref('cleaned')
const profileCollapseActive = ref(['base', 'deep', 'metrics'])
const articlePollingTimer = ref<number | null>(null)
const profilePollingTimer = ref<number | null>(null)
type ProfileFieldKey = keyof StyleProfilePayload
interface ProfileFieldConfig {
  key: ProfileFieldKey
  label: string
  wide?: boolean
  rows?: number
}

const baseProfileFields: ProfileFieldConfig[] = [
  { key: 'summary', label: '总体风格描述', wide: true, rows: 4 },
  { key: 'sentence_style', label: '句式特点' },
  { key: 'structure_style', label: '段落结构' },
  { key: 'rhetoric_style', label: '常用修辞' },
  { key: 'imagery_style', label: '常用意象' },
  { key: 'vocabulary_style', label: '常用词汇' },
  { key: 'tone_style', label: '情绪色彩' },
  { key: 'argument_style', label: '论证方式' },
  { key: 'opening_style', label: '开头方式' },
  { key: 'ending_style', label: '结尾方式' },
  { key: 'do_rules', label: '应该遵守', wide: true, rows: 4 },
  { key: 'dont_rules', label: '禁止事项', wide: true, rows: 4 },
  { key: 'prompt_instruction', label: '模仿指令', wide: true, rows: 5 },
]
const deepProfileFields: ProfileFieldConfig[] = [
  { key: 'syntax_fingerprint', label: '句法指纹', rows: 4 },
  { key: 'punctuation_fingerprint', label: '标点习惯', rows: 4 },
  { key: 'preferred_words', label: '词汇偏好库', wide: true, rows: 4 },
  { key: 'structure_template', label: '结构模板', wide: true, rows: 4 },
  { key: 'style_constraints', label: '风格约束', wide: true, rows: 4 },
]
const profileFields: ProfileFieldConfig[] = [...baseProfileFields, ...deepProfileFields]
const profileForm = ref<Record<ProfileFieldKey, string>>(emptyProfileForm())

const profileMetrics = computed<Record<string, unknown>>(() => {
  const loaded = store.currentProfileMetrics?.metrics
  if (loaded && Object.keys(loaded).length > 0) return loaded
  const fromProfile = store.currentProfile?.profile?.profile_json?.deep_metrics
  return isRecord(fromProfile) ? fromProfile : {}
})
const hasMetrics = computed(() => Object.keys(profileMetrics.value).length > 0)
const dominantMarks = computed(() => {
  const marks = getNested(profileMetrics.value, ['punctuation', 'dominant_marks'])
  return Array.isArray(marks) && marks.length > 0 ? marks.join('、') : '暂无'
})
const structureTags = computed(() => {
  const tags = getNested(profileMetrics.value, ['structure', 'tags'])
  return Array.isArray(tags) && tags.length > 0 ? tags.join('、') : '暂无'
})
const hasProcessingArticles = computed(() => store.articles.some((article) => isArticleProcessing(article.status)))
const profileRuntimeJson = computed(() => store.currentProfile?.profile?.profile_json || {})
const profileGenerationStatus = computed(() => {
  const status = profileRuntimeJson.value.profile_generation_status
  return typeof status === 'string' ? status : ''
})
const profileGenerationError = computed(() => {
  const error = profileRuntimeJson.value.profile_generation_error
  return typeof error === 'string' ? error : ''
})
const isProfileGenerating = computed(() => profileGenerationStatus.value === 'running')

onMounted(() => {
  store.loadStyleDetail(props.id).then(() => {
    if (hasProcessingArticles.value) startArticlePolling()
    if (isProfileGenerating.value) startProfilePolling()
  })
})

onBeforeUnmount(() => {
  stopArticlePolling()
  stopProfilePolling()
})

watch(
  () => props.id,
  (id) => {
    selectedFile.value = null
    uploadRef.value?.clearFiles()
    stopArticlePolling()
    stopProfilePolling()
    store.loadStyleDetail(id).then(() => {
      if (hasProcessingArticles.value) startArticlePolling()
      if (isProfileGenerating.value) startProfilePolling()
    })
  },
)

function handleFileChange(uploadFile: UploadFile) {
  selectedFile.value = uploadFile.raw ?? null
}

async function handleUpload() {
  if (!selectedFile.value) return
  await store.uploadStyleArticle(props.id, selectedFile.value)
  selectedFile.value = null
  uploadRef.value?.clearFiles()
  startArticlePolling()
  ElMessage.success('文章已上传，正在后台处理')
}

async function handleUpdateStyle(payload: StyleCreatePayload) {
  if (!store.currentStyle) return
  submitting.value = true
  try {
    await store.editStyle(store.currentStyle.id, payload)
    dialogOpen.value = false
    ElMessage.success('风格已更新')
  } finally {
    submitting.value = false
  }
}

async function handleArticleClick(article: SourceArticle) {
  activeArticleTab.value = 'cleaned'
  articleDialogOpen.value = true
  await store.loadArticleDetail(props.id, article.id)
}

async function handleDeleteArticle(article: SourceArticle) {
  try {
    await ElMessageBox.confirm(`确认删除文章“${article.title}”？其包含的分段数据也会被永久删除。`, '删除文章', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await store.removeArticle(props.id, article.id)
    ElMessage.success('文章已删除')
  } catch {
    // User cancelled
  }
}

async function handleGenerateProfile() {
  if (!store.currentProfile?.can_generate) return
  try {
    if (store.currentProfile.is_stale) {
      await ElMessageBox.confirm('当前风格画像可能已过期，确认重新分析并覆盖现有画像？', '重新分析风格', {
        confirmButtonText: '重新分析',
        cancelButtonText: '取消',
        type: 'warning',
      })
    }
    await store.regenerateStyleProfile(props.id)
    startProfilePolling()
    ElMessage.success('风格画像分析已开始')
  } catch {
    // User cancelled or API error has been handled globally.
  }
}

function openProfileDialog() {
  const profile = store.currentProfile?.profile
  profileForm.value = emptyProfileForm()
  if (profile) {
    for (const field of profileFields) {
      profileForm.value[field.key] = profile[field.key] || ''
    }
  }
  profileDialogOpen.value = true
}

async function handleSaveProfile() {
  const payload: StyleProfilePayload = { ...profileForm.value }
  await store.saveStyleProfile(props.id, payload)
  profileDialogOpen.value = false
  ElMessage.success('风格画像已保存')
}

function emptyProfileForm() {
  return profileFields.reduce(
    (result, field) => {
      result[field.key] = ''
      return result
    },
    {} as Record<ProfileFieldKey, string>,
  )
}

function startArticlePolling() {
  if (articlePollingTimer.value !== null) return
  articlePollingTimer.value = window.setInterval(async () => {
    await store.loadStyleDetail(props.id)
    if (!hasProcessingArticles.value) {
      stopArticlePolling()
      if (store.articles.some((article) => article.status === 'failed')) {
        ElMessage.warning('有文章后台处理失败，请查看后端日志')
      }
    }
  }, 2500)
}

function stopArticlePolling() {
  if (articlePollingTimer.value === null) return
  window.clearInterval(articlePollingTimer.value)
  articlePollingTimer.value = null
}

function startProfilePolling() {
  if (profilePollingTimer.value !== null) return
  profilePollingTimer.value = window.setInterval(async () => {
    await store.loadStyleProfile(props.id)
    if (!isProfileGenerating.value) {
      stopProfilePolling()
      if (profileGenerationStatus.value === 'failed') {
        ElMessage.error(profileGenerationError.value || '风格画像分析失败')
      } else if (profileGenerationStatus.value === 'completed') {
        ElMessage.success('风格画像分析完成')
      }
    }
  }, 3000)
}

function stopProfilePolling() {
  if (profilePollingTimer.value === null) return
  window.clearInterval(profilePollingTimer.value)
  profilePollingTimer.value = null
}

function isArticleProcessing(status: string) {
  return ['uploaded', 'cleaning', 'chunking', 'embedding', 'analyzing'].includes(status)
}

function metricValue(section: string, key: string) {
  const value = getNested(profileMetrics.value, [section, key])
  return typeof value === 'number' ? value : '暂无'
}

function metricRatio(section: string, key: string) {
  const value = getNested(profileMetrics.value, [section, key])
  return typeof value === 'number' ? `${(value * 100).toFixed(1)}%` : '暂无'
}

function punctuationPerThousand(key: string) {
  const value = getNested(profileMetrics.value, ['punctuation', 'per_1000_chars', key])
  return typeof value === 'number' ? value : '暂无'
}

function topMetricItems(key: string) {
  const items = getNested(profileMetrics.value, ['vocabulary', key])
  if (!Array.isArray(items) || items.length === 0) return '暂无'
  return items
    .slice(0, 12)
    .map((item) => (isRecord(item) ? `${item.text}${typeof item.count === 'number' ? `(${item.count})` : ''}` : ''))
    .filter(Boolean)
    .join('、')
}

function getNested(source: unknown, path: string[]) {
  return path.reduce<unknown>((current, key) => (isRecord(current) ? current[key] : undefined), source)
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === 'object' && !Array.isArray(value))
}

function formatProfileValue(value: string | null | undefined) {
  return value?.trim() || '暂未填写'
}

function statusTagType(value: string) {
  if (value === 'completed') return 'success'
  if (value === 'failed') return 'danger'
  if (value === 'uploaded') return 'info'
  return 'warning'
}

function formatSourceType(value?: string) {
  const labels: Record<string, string> = {
    txt: 'TXT',
    markdown: 'Markdown',
    docx: 'DOCX',
  }
  return value ? labels[value] || value : ''
}

function formatChunkPosition(value: unknown) {
  const labels: Record<string, string> = {
    beginning: '开头',
    middle: '中段',
    end: '结尾',
  }
  return typeof value === 'string' ? labels[value] || value : '未知位置'
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat('zh-CN', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
}
</script>
