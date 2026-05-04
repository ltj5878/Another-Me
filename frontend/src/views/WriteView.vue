<template>
  <section class="page">
    <header class="page-header">
      <div>
        <p class="eyebrow">Writing Desk</p>
        <h1>写文章</h1>
        <p class="page-copy">选择风格，填写写作要求，生成正文后可以继续改写、保留历史版本，并调试完整 Prompt。</p>
      </div>
    </header>

    <section class="writer-surface">
      <el-form label-position="top" class="writer-form">
        <el-form-item label="选择风格">
          <el-select v-model="form.styleId" placeholder="请选择风格" filterable>
            <el-option v-for="style in store.styles" :key="style.id" :label="style.name" :value="style.id" />
          </el-select>
        </el-form-item>

        <div class="writer-form-row">
          <el-form-item label="写作类型">
            <el-select v-model="form.writingType">
              <el-option v-for="option in writingTypes" :key="option" :label="option" :value="option" />
            </el-select>
          </el-form-item>
          <el-form-item v-if="form.writingType === '自定义'" label="自定义类型">
            <el-input v-model="form.customWritingType" placeholder="例如：公众号长文" />
          </el-form-item>
        </div>

        <el-form-item label="输入内容">
          <el-input
            v-model="form.userInput"
            type="textarea"
            :rows="6"
            placeholder="输入题目、问题、选题、隐喻、观点。例如：为什么人在城市里越来越难保持真诚；把城市生活比作潮湿的抽屉。"
          />
        </el-form-item>

        <div class="writer-form-row">
          <el-form-item label="文章长度">
            <el-select v-model="form.lengthPreset">
              <el-option v-for="option in lengthPresets" :key="option" :label="option" :value="option" />
            </el-select>
          </el-form-item>
          <el-form-item v-if="form.lengthPreset === '自定义'" label="自定义字数">
            <el-input-number v-model="form.customWordCount" :min="100" :max="10000" :step="100" controls-position="right" />
          </el-form-item>
        </div>

        <el-form-item label="语气强度">
          <el-segmented v-model="form.imitationStrength" :options="imitationStrengths" />
        </el-form-item>

        <el-form-item label="是否引用旧文片段">
          <el-switch v-model="form.includeReferences" active-text="引用" inactive-text="不引用" />
        </el-form-item>

        <el-form-item label="补充要求">
          <el-input v-model="form.extraRequirements" type="textarea" :rows="3" placeholder="可选，例如：不要鸡汤；结尾留一个余味；观点更克制。" />
        </el-form-item>

        <el-button type="primary" :icon="EditPen" :loading="generating" @click="handleGenerate">
          {{ generating ? '生成中' : '生成文章' }}
        </el-button>
      </el-form>

      <aside class="writer-note">
        <h2>风格画像</h2>
        <div v-if="store.profileLoading" class="writer-muted">正在读取画像...</div>
        <template v-else-if="selectedProfile">
          <p>{{ selectedProfile.summary || '这个风格还没有总体描述。' }}</p>
          <div v-if="selectedDeepSummary" class="writer-deep-summary">{{ selectedDeepSummary }}</div>
          <el-tag v-if="store.currentProfile?.is_stale" class="writer-tag" type="warning" effect="plain">画像可能已过期</el-tag>
          <el-tag v-else class="writer-tag" type="success" effect="plain">已加载 v{{ selectedProfile.version }}</el-tag>
        </template>
        <p v-else>这个风格还没有画像。请先在风格详情页上传至少 3 篇文章并重新分析风格。</p>

        <div class="history-block">
          <h2>最近生成</h2>
          <div v-if="historyLoading" class="writer-muted">正在读取历史...</div>
          <div v-else-if="generationHistory.length > 0" class="history-list">
            <div v-for="item in generationHistory" :key="item.id" class="history-item">
              <button class="history-main" type="button" @click="selectHistory(item)">
                <strong>{{ formatHistoryTitle(item) }}</strong>
                <span>{{ formatOperationLabel(item) }} · {{ formatDate(item.created_at) }}</span>
              </button>
              <el-button class="history-delete" type="danger" plain :icon="Delete" circle @click.stop="handleDeleteHistory(item)" />
            </div>
          </div>
          <p v-else>还没有生成记录。</p>
        </div>
      </aside>
    </section>

    <section class="panel result-panel">
      <div class="panel-header">
        <div>
          <h2>生成结果</h2>
          <p>每次改写都会保存为一条新的生成历史，不覆盖当前记录。</p>
        </div>
        <div class="result-actions">
          <el-button :icon="Download" :disabled="!displayedContent || isStreaming" @click="exportMarkdown">导出 Markdown</el-button>
          <el-button :icon="DocumentCopy" :disabled="!displayedContent" @click="copyResult">复制正文</el-button>
        </div>
      </div>

      <div v-if="currentGeneration?.output?.content" class="revision-toolbar">
        <el-button
          v-for="operation in reviseOperations"
          :key="operation.type"
          size="small"
          :loading="operationLoading === operation.type"
          :disabled="isStreaming"
          @click="handleRevision(operation.type)"
        >
          {{ operation.label }}
        </el-button>
      </div>

      <div v-if="isStreaming" class="stream-status">{{ streamingStatus }}</div>
      <pre v-if="displayedContent" class="generated-content">{{ displayedContent }}</pre>
      <el-empty v-else description="填写要求并点击生成文章后，这里会显示正文" />
    </section>

    <section class="panel prompt-panel">
      <div class="panel-header">
        <div>
          <h2>Prompt 调试台</h2>
          <p>查看完整 Prompt、风格画像、检索片段和结果，也可以改 Prompt 后生成新记录。</p>
        </div>
        <el-button type="primary" plain :loading="debugRunning" :disabled="!form.styleId || !debugSystemPrompt || !debugUserPrompt" @click="handleDebugRun">
          用调试 Prompt 重新生成
        </el-button>
      </div>

      <el-tabs class="debug-tabs">
        <el-tab-pane label="System Prompt">
          <el-input v-model="debugSystemPrompt" type="textarea" :rows="8" />
        </el-tab-pane>
        <el-tab-pane label="User Prompt">
          <el-input v-model="debugUserPrompt" type="textarea" :rows="14" />
        </el-tab-pane>
        <el-tab-pane label="风格画像">
          <pre class="prompt-preview">{{ debugStyleProfileText }}</pre>
        </el-tab-pane>
        <el-tab-pane :label="`检索片段 (${debugRetrievedChunks.length})`">
          <el-alert
            v-if="currentGeneration"
            class="retrieval-alert"
            :type="retrievalAlertType"
            :closable="false"
            :title="retrievalSummaryText"
          />
          <div v-if="debugRetrievedChunks.length > 0" class="debug-chunk-list">
            <article v-for="chunk in debugRetrievedChunks" :key="chunk.id || chunk.chunk_index" class="debug-chunk-item">
              <header>
                <strong>#{{ Number(chunk.chunk_index ?? 0) + 1 }}</strong>
                <span v-if="typeof chunk.similarity === 'number'">相似度 {{ chunk.similarity.toFixed(3) }}</span>
                <span v-if="typeof chunk.style_score === 'number'">风格分 {{ chunk.style_score.toFixed(2) }}</span>
                <span v-if="typeof chunk.semantic_score === 'number'">语义分 {{ chunk.semantic_score.toFixed(2) }}</span>
                <el-tag v-if="chunk.retrieval_strategy" effect="plain" size="small">{{ formatRetrievalStrategy(chunk.retrieval_strategy) }}</el-tag>
              </header>
              <p v-if="chunk.rerank_reason" class="debug-rerank-reason">{{ chunk.rerank_reason }}</p>
              <pre>{{ chunk.content }}</pre>
            </article>
          </div>
          <el-empty v-else :description="debugChunksEmptyText" />
        </el-tab-pane>
        <el-tab-pane label="最终结果">
          <pre v-if="displayedContent" class="generated-content">{{ displayedContent }}</pre>
          <el-empty v-else description="还没有生成结果" />
        </el-tab-pane>
      </el-tabs>
    </section>

    <el-dialog v-model="rewriteDialogOpen" title="继续改写" width="620px">
      <el-form label-position="top">
        <el-form-item label="修改指令">
          <el-input
            v-model="rewriteInstruction"
            type="textarea"
            :rows="5"
            placeholder="例如：保留核心意思，但把开头改得更像一个真实生活场景，结尾更克制。"
          />
        </el-form-item>
        <el-form-item label="是否重新引用旧文片段">
          <el-switch v-model="rewriteIncludeReferences" active-text="引用" inactive-text="不引用" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="rewriteDialogOpen = false">取消</el-button>
        <el-button type="primary" :loading="operationLoading === 'rewrite'" @click="submitRewrite">生成改写版本</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup lang="ts">
import { Delete, DocumentCopy, Download, EditPen } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onMounted, reactive, ref, watch } from 'vue'

import {
  deleteGeneration,
  fetchGeneration,
  fetchGenerations,
  streamCreateGeneration,
  streamDebugRunGeneration,
  streamReviseGeneration,
} from '@/api/generations'
import { useStylesStore } from '@/stores/styles'
import type { Generation, GenerationCreatePayload, GenerationDebugRunPayload, GenerationRevisePayload, StyleProfile } from '@/types/api'

interface DebugChunk {
  id?: string
  chunk_index?: number
  similarity?: number
  style_score?: number | null
  semantic_score?: number | null
  rerank_reason?: string | null
  retrieval_strategy?: string | null
  content?: string
}

const store = useStylesStore()
const writingTypes = ['散文', '时评', '问答', '短评', '评论', '自定义']
const lengthPresets = ['短', '中', '长', '自定义']
const imitationStrengths = ['轻微模仿', '中度模仿', '高度模仿']
const reviseOperations = [
  { type: 'regenerate', label: '重新生成' },
  { type: 'rewrite', label: '继续改写' },
  { type: 'shorten', label: '缩短' },
  { type: 'expand', label: '扩写' },
  { type: 'sharper', label: '更尖锐' },
  { type: 'more_restrained', label: '更克制' },
  { type: 'more_like_style', label: '更像原风格' },
  { type: 'reduce_imitation_trace', label: '降低模仿痕迹' },
  { type: 'revise_opening', label: '修改开头' },
  { type: 'revise_ending', label: '修改结尾' },
]
const generating = ref(false)
const historyLoading = ref(false)
const operationLoading = ref('')
const debugRunning = ref(false)
const generationHistory = ref<Generation[]>([])
const currentGeneration = ref<Generation | null>(null)
const streamingContent = ref('')
const streamingStatus = ref('正在连接生成服务...')
const selectingHistory = ref(false)
const debugSystemPrompt = ref('')
const debugUserPrompt = ref('')
const rewriteDialogOpen = ref(false)
const rewriteInstruction = ref('')
const rewriteIncludeReferences = ref(true)
const form = reactive({
  styleId: '',
  writingType: '散文',
  customWritingType: '',
  userInput: '',
  lengthPreset: '中',
  customWordCount: 1200,
  imitationStrength: '中度模仿',
  includeReferences: true,
  extraRequirements: '',
})

onMounted(async () => {
  if (store.styles.length === 0) {
    await store.loadStyles()
  }
  await loadGenerationHistory()
})

watch(
  () => form.styleId,
  async (styleId) => {
    if (!selectingHistory.value) {
      currentGeneration.value = null
      streamingContent.value = ''
      streamingStatus.value = '正在连接生成服务...'
    }
    refreshDebugPrompts()
    if (styleId) {
      await Promise.all([store.loadStyleProfile(styleId), loadGenerationHistory(styleId)])
      refreshDebugPrompts()
    } else {
      await loadGenerationHistory()
    }
  },
)

watch(currentGeneration, () => {
  refreshDebugPrompts()
})

const selectedStyle = computed(() => store.styles.find((style) => style.id === form.styleId) || null)
const selectedProfile = computed(() => (store.currentProfile?.style_category_id === form.styleId ? store.currentProfile.profile : null))
const selectedDeepSummary = computed(() => {
  const profile = selectedProfile.value
  if (!profile) return ''
  const parts = [profile.syntax_fingerprint, profile.punctuation_fingerprint, profile.structure_template]
    .map((value) => value?.trim())
    .filter(Boolean)
  return parts.slice(0, 2).join('；')
})
const localPromptPreview = computed(() => {
  if (!selectedStyle.value || !selectedProfile.value || !form.userInput.trim()) return ''
  return [
    '【System Prompt】',
    defaultSystemPrompt(),
    '',
    '【User Prompt】',
    `风格名称：${selectedStyle.value.name}`,
    `写作类型：${resolvedWritingType.value}`,
    `文章长度：${resolvedLength.value}`,
    `语气强度：${form.imitationStrength}`,
    `是否引用旧文片段：${form.includeReferences ? '是' : '否'}`,
    '',
    '【风格画像】',
    formatProfile(selectedProfile.value),
    '',
    '【用户要求】',
    form.userInput.trim(),
    '',
    '【补充要求】',
    form.extraRequirements.trim() || '无',
  ].join('\n')
})
const resolvedWritingType = computed(() => (form.writingType === '自定义' ? form.customWritingType.trim() || '自定义' : form.writingType))
const resolvedLength = computed(() => (form.lengthPreset === '自定义' ? `约 ${form.customWordCount} 字` : form.lengthPreset))
const currentMetadata = computed(() => currentGeneration.value?.output?.metadata_json || {})
const debugRetrievedChunks = computed<DebugChunk[]>(() => {
  const chunks = currentMetadata.value.retrieved_chunks
  return Array.isArray(chunks) ? (chunks as DebugChunk[]) : []
})
const debugChunksEmptyText = computed(() => {
  if (!currentGeneration.value) return '还没有选择生成记录'
  if (currentMetadata.value.include_references === false) return '本次生成未开启“引用旧文片段”，所以没有检索片段'
  return '本次生成没有检索到可用片段'
})
const retrievalSummaryText = computed(() => {
  const strategy = currentMetadata.value.retrieval_strategy
  if (strategy === 'smart_rerank') {
    return `Smart Retrieval：已从 ${currentMetadata.value.candidate_chunk_count || debugRetrievedChunks.value.length} 个语义候选中重排出 ${debugRetrievedChunks.value.length} 个风格示例片段`
  }
  if (strategy === 'semantic_fallback') {
    return `已降级为语义检索：当前展示 ${debugRetrievedChunks.value.length} 个语义相关片段`
  }
  if (strategy === 'disabled') return '本次生成未开启旧文片段引用'
  return '当前生成记录没有检索策略信息'
})
const retrievalAlertType = computed(() => (currentMetadata.value.retrieval_strategy === 'smart_rerank' ? 'success' : 'info'))
const isStreaming = computed(() => generating.value || Boolean(operationLoading.value) || debugRunning.value)
const displayedContent = computed(() => streamingContent.value || currentGeneration.value?.output?.content || '')
const debugStyleProfileText = computed(() => {
  const snapshot = currentMetadata.value.style_profile_snapshot
  if (snapshot && typeof snapshot === 'object') {
    return Object.entries(snapshot as Record<string, unknown>)
      .filter(([, value]) => typeof value === 'string' && value.trim())
      .map(([key, value]) => `${key}: ${value}`)
      .join('\n')
  }
  return selectedProfile.value ? formatProfile(selectedProfile.value) : '还没有风格画像'
})

async function loadGenerationHistory(styleId = form.styleId) {
  historyLoading.value = true
  try {
    generationHistory.value = await fetchGenerations(styleId || undefined, 20)
  } finally {
    historyLoading.value = false
  }
}

async function handleGenerate() {
  if (!validateBaseForm()) return

  generating.value = true
  let streamErrorShown = false
  try {
    const payload: GenerationCreatePayload = {
      style_category_id: form.styleId,
      writing_type: form.writingType,
      custom_writing_type: form.writingType === '自定义' ? form.customWritingType.trim() : null,
      user_input: form.userInput.trim(),
      length_preset: form.lengthPreset,
      custom_word_count: form.lengthPreset === '自定义' ? form.customWordCount : null,
      imitation_strength: form.imitationStrength,
      include_references: form.includeReferences,
      extra_requirements: form.extraRequirements.trim() || null,
    }
    currentGeneration.value = null
    streamingContent.value = ''
    streamingStatus.value = '正在连接生成服务...'
    await streamCreateGeneration(payload, {
      onProgress: (message) => {
        streamingStatus.value = message
      },
      onDelta: (content) => {
        streamingStatus.value = '正在流式输出正文...'
        streamingContent.value += content
      },
      onCompleted: async (generation) => {
        currentGeneration.value = generation
        streamingContent.value = ''
        await loadGenerationHistory(form.styleId)
        ElMessage.success('文章已生成')
      },
      onError: (message) => {
        streamErrorShown = true
        ElMessage.error(message)
      },
    })
  } catch (error) {
    if (!streamErrorShown) {
      ElMessage.error(error instanceof Error ? error.message : '流式生成失败')
    }
  } finally {
    generating.value = false
  }
}

function validateBaseForm() {
  if (!form.styleId) {
    ElMessage.warning('请先选择风格')
    return false
  }
  if (!form.userInput.trim()) {
    ElMessage.warning('请填写输入内容')
    return false
  }
  if (form.writingType === '自定义' && !form.customWritingType.trim()) {
    ElMessage.warning('请填写自定义写作类型')
    return false
  }
  if (!selectedProfile.value) {
    ElMessage.warning('当前风格还没有画像，先到风格详情页生成或手动编辑画像')
    return false
  }
  return true
}

async function selectHistory(item: Generation) {
  selectingHistory.value = true
  try {
    const latest = await fetchGeneration(item.id)
    currentGeneration.value = latest
    streamingContent.value = ''
    streamingStatus.value = '正在连接生成服务...'
    const metadata = latest.output?.metadata_json || {}
    form.styleId = latest.style_category_id
    form.userInput = typeof metadata.user_input === 'string' ? metadata.user_input : form.userInput
    form.writingType = typeof metadata.writing_type === 'string' ? metadata.writing_type : form.writingType
    form.customWritingType = typeof metadata.custom_writing_type === 'string' ? metadata.custom_writing_type : ''
    form.lengthPreset = typeof metadata.length_preset === 'string' ? metadata.length_preset : form.lengthPreset
    form.customWordCount = typeof metadata.custom_word_count === 'number' ? metadata.custom_word_count : form.customWordCount
    form.imitationStrength = typeof metadata.imitation_strength === 'string' ? metadata.imitation_strength : form.imitationStrength
    form.includeReferences = typeof metadata.include_references === 'boolean' ? metadata.include_references : form.includeReferences
    form.extraRequirements = typeof metadata.extra_requirements === 'string' ? metadata.extra_requirements : ''
  } finally {
    queueMicrotask(() => {
      selectingHistory.value = false
    })
  }
}

async function handleRevision(operationType: string) {
  if (!currentGeneration.value) return
  if (operationType === 'rewrite') {
    rewriteInstruction.value = ''
    rewriteIncludeReferences.value = true
    rewriteDialogOpen.value = true
    return
  }
  await runRevision({ operation_type: operationType, custom_instruction: null, include_references: form.includeReferences })
}

async function submitRewrite() {
  if (!rewriteInstruction.value.trim()) {
    ElMessage.warning('请填写修改指令')
    return
  }
  await runRevision({
    operation_type: 'rewrite',
    custom_instruction: rewriteInstruction.value.trim(),
    include_references: rewriteIncludeReferences.value,
  })
  rewriteDialogOpen.value = false
}

async function runRevision(payload: GenerationRevisePayload) {
  if (!currentGeneration.value) return
  operationLoading.value = payload.operation_type
  let streamErrorShown = false
  try {
    const sourceId = currentGeneration.value.id
    streamingContent.value = ''
    streamingStatus.value = '正在连接生成服务...'
    await streamReviseGeneration(sourceId, payload, {
      onProgress: (message) => {
        streamingStatus.value = message
      },
      onDelta: (content) => {
        streamingStatus.value = '正在流式输出正文...'
        streamingContent.value += content
      },
      onCompleted: async (generation) => {
        currentGeneration.value = generation
        streamingContent.value = ''
        await loadGenerationHistory(form.styleId)
        ElMessage.success(`${formatOperationType(payload.operation_type)}版本已生成`)
      },
      onError: (message) => {
        streamErrorShown = true
        ElMessage.error(message)
      },
    })
  } catch (error) {
    if (!streamErrorShown) {
      ElMessage.error(error instanceof Error ? error.message : '流式改写失败')
    }
  } finally {
    operationLoading.value = ''
  }
}

async function handleDebugRun() {
  if (!form.styleId || !debugSystemPrompt.value.trim() || !debugUserPrompt.value.trim()) return
  debugRunning.value = true
  let streamErrorShown = false
  try {
    const payload: GenerationDebugRunPayload = {
      style_category_id: form.styleId,
      system_prompt: debugSystemPrompt.value.trim(),
      user_prompt: debugUserPrompt.value.trim(),
      source_generation_id: currentGeneration.value?.id || null,
    }
    streamingContent.value = ''
    streamingStatus.value = '正在连接生成服务...'
    await streamDebugRunGeneration(payload, {
      onProgress: (message) => {
        streamingStatus.value = message
      },
      onDelta: (content) => {
        streamingStatus.value = '正在流式输出正文...'
        streamingContent.value += content
      },
      onCompleted: async (generation) => {
        currentGeneration.value = generation
        streamingContent.value = ''
        await loadGenerationHistory(form.styleId)
        ElMessage.success('Prompt 调试版本已生成')
      },
      onError: (message) => {
        streamErrorShown = true
        ElMessage.error(message)
      },
    })
  } catch (error) {
    if (!streamErrorShown) {
      ElMessage.error(error instanceof Error ? error.message : 'Prompt 调试生成失败')
    }
  } finally {
    debugRunning.value = false
  }
}

async function handleDeleteHistory(item: Generation) {
  try {
    await ElMessageBox.confirm(`确认删除生成记录“${formatHistoryTitle(item)}”？`, '删除生成历史', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await deleteGeneration(item.id)
    generationHistory.value = generationHistory.value.filter((historyItem) => historyItem.id !== item.id)
    if (currentGeneration.value?.id === item.id) {
      currentGeneration.value = null
    }
    ElMessage.success('生成记录已删除')
  } catch {
    // User cancelled or API error has been handled globally.
  }
}

async function copyResult() {
  const content = displayedContent.value
  if (!content) return
  await navigator.clipboard.writeText(content)
  ElMessage.success('正文已复制')
}

function exportMarkdown() {
  const generation = currentGeneration.value
  const content = generation?.output?.content
  if (!generation || !content) return
  const title = formatHistoryTitle(generation)
  const markdown = [
    `# ${title}`,
    '',
    `- 生成时间：${formatDate(generation.created_at)}`,
    `- 操作类型：${formatOperationLabel(generation)}`,
    '',
    content,
  ].join('\n')
  const blob = new Blob([markdown], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `${sanitizeFilename(title)}.md`
  link.click()
  URL.revokeObjectURL(url)
}

function refreshDebugPrompts() {
  const metadata = currentGeneration.value?.output?.metadata_json || {}
  if (typeof metadata.system_prompt === 'string' && typeof metadata.user_prompt === 'string') {
    debugSystemPrompt.value = metadata.system_prompt
    debugUserPrompt.value = metadata.user_prompt
    return
  }
  const split = splitStoredPrompt(currentGeneration.value?.prompt || '')
  if (split.systemPrompt || split.userPrompt) {
    debugSystemPrompt.value = split.systemPrompt
    debugUserPrompt.value = split.userPrompt
    return
  }
  const preview = splitStoredPrompt(localPromptPreview.value)
  debugSystemPrompt.value = preview.systemPrompt || defaultSystemPrompt()
  debugUserPrompt.value = preview.userPrompt
}

function splitStoredPrompt(prompt: string) {
  const systemMarker = '【System Prompt】'
  const userMarker = '【User Prompt】'
  const systemIndex = prompt.indexOf(systemMarker)
  const userIndex = prompt.indexOf(userMarker)
  if (systemIndex === -1 || userIndex === -1) {
    return { systemPrompt: '', userPrompt: prompt }
  }
  return {
    systemPrompt: prompt.slice(systemIndex + systemMarker.length, userIndex).trim(),
    userPrompt: prompt.slice(userIndex + userMarker.length).trim(),
  }
}

function defaultSystemPrompt() {
  return '你是一个中文写作助手，任务是根据指定风格生成文章。请根据风格画像生成自然、完整、可发表的正文。'
}

function formatProfile(profile: StyleProfile | null) {
  if (!profile) return '未填写'
  return [
    `总体风格：${profile.summary || '未填写'}`,
    `句式特点：${profile.sentence_style || '未填写'}`,
    `段落结构：${profile.structure_style || '未填写'}`,
    `常用修辞：${profile.rhetoric_style || '未填写'}`,
    `常用意象：${profile.imagery_style || '未填写'}`,
    `常用词汇：${profile.vocabulary_style || '未填写'}`,
    `情绪色彩：${profile.tone_style || '未填写'}`,
    `论证方式：${profile.argument_style || '未填写'}`,
    `开头方式：${profile.opening_style || '未填写'}`,
    `结尾方式：${profile.ending_style || '未填写'}`,
    `必须遵守：${profile.do_rules || '未填写'}`,
    `禁止事项：${profile.dont_rules || '未填写'}`,
    `模仿指令：${profile.prompt_instruction || '未填写'}`,
    `句法指纹：${profile.syntax_fingerprint || '未填写'}`,
    `标点习惯：${profile.punctuation_fingerprint || '未填写'}`,
    `词汇偏好库：${profile.preferred_words || '未填写'}`,
    `结构模板：${profile.structure_template || '未填写'}`,
    `风格约束：${profile.style_constraints || '未填写'}`,
  ].join('\n')
}

function formatRetrievalStrategy(value: string) {
  const labels: Record<string, string> = {
    smart_rerank: '风格重排',
    semantic_fallback: '语义降级',
    disabled: '未检索',
  }
  return labels[value] || value
}

function formatHistoryTitle(item: Generation) {
  const metadata = item.output?.metadata_json || {}
  const displayTitle = typeof metadata.display_title === 'string' ? metadata.display_title : ''
  const userInput = typeof metadata.user_input === 'string' ? metadata.user_input : ''
  if (displayTitle.trim()) return displayTitle.trim()
  return userInput.trim() ? userInput.trim().slice(0, 24) : `生成记录 ${item.id.slice(0, 8)}`
}

function formatOperationLabel(item: Generation) {
  const label = item.output?.metadata_json?.operation_label
  return typeof label === 'string' ? label : '初次生成'
}

function formatOperationType(type: string) {
  const operation = reviseOperations.find((item) => item.type === type)
  return operation?.label || '改写'
}

function sanitizeFilename(value: string) {
  return value.replace(/[\\/:*?"<>|]/g, '-').replace(/\s+/g, ' ').trim() || 'generation'
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat('zh-CN', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
}
</script>
