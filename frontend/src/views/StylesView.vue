<template>
  <section class="page">
    <header class="page-header">
      <div>
        <p class="eyebrow">Style Categories</p>
        <h1>风格库</h1>
        <p class="page-copy">管理写作风格与对应素材文章。</p>
      </div>
      <el-button type="primary" :icon="Plus" @click="openCreateDialog">新建风格</el-button>
    </header>

    <el-table
      v-if="store.loading || store.styles.length > 0"
      v-loading="store.loading"
      :data="store.styles"
      class="data-table styles-table"
      row-key="id"
      table-layout="fixed"
    >
      <el-table-column prop="name" label="风格名称" min-width="220" show-overflow-tooltip>
        <template #default="scope">
          <RouterLink v-if="scope?.row" class="table-link" :to="`/styles/${scope.row.id}`">{{ scope.row.name }}</RouterLink>
        </template>
      </el-table-column>
      <el-table-column prop="writing_type_hint" label="类型" width="120" align="center">
        <template #default="scope">
          <el-tag v-if="scope?.row" class="style-type-tag" effect="plain">{{ scope.row.writing_type_hint }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="article_count" label="文章" width="88" align="center" />
      <el-table-column label="最近上传" width="150" align="center">
        <template #default="scope">{{ scope?.row?.last_article_at ? formatDate(scope.row.last_article_at) : '暂无' }}</template>
      </el-table-column>
      <el-table-column label="创建时间" width="150" align="center">
        <template #default="scope">{{ scope?.row ? formatDate(scope.row.created_at) : '' }}</template>
      </el-table-column>
      <el-table-column label="操作" width="170" align="center" header-align="center">
        <template #default="scope">
          <div v-if="scope?.row" class="table-actions">
            <el-button text type="primary" @click="$router.push(`/styles/${scope.row.id}`)">查看</el-button>
            <el-button text type="primary" @click="openEditDialog(scope.row)">编辑</el-button>
            <el-button text type="danger" @click="handleDelete(scope.row.id, scope.row.name)">删除</el-button>
          </div>
        </template>
      </el-table-column>
    </el-table>

    <el-alert
      v-else
      class="empty-alert"
      title="还没有风格分类"
      description="创建一个风格后，就可以上传对应文章。"
      type="info"
      :closable="false"
      show-icon
    />

    <StyleFormDialog
      v-model="dialogOpen"
      :mode="dialogMode"
      :style="editingStyle"
      :saving="submitting"
      @submit="handleSubmitStyle"
    />
  </section>
</template>

<script setup lang="ts">
import { Plus } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import StyleFormDialog from '@/components/StyleFormDialog.vue'
import { useStylesStore } from '@/stores/styles'
import type { StyleCategory, StyleCreatePayload } from '@/types/api'

const store = useStylesStore()
const router = useRouter()
const dialogOpen = ref(false)
const dialogMode = ref<'create' | 'edit'>('create')
const editingStyle = ref<StyleCategory | null>(null)
const submitting = ref(false)

onMounted(() => {
  store.loadStyles()
})

function formatDate(value: string) {
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value))
}

function openCreateDialog() {
  dialogMode.value = 'create'
  editingStyle.value = null
  dialogOpen.value = true
}

function openEditDialog(style: StyleCategory) {
  dialogMode.value = 'edit'
  editingStyle.value = style
  dialogOpen.value = true
}

async function handleSubmitStyle(payload: StyleCreatePayload) {
  submitting.value = true
  try {
    if (dialogMode.value === 'create') {
      const created = await store.addStyle(payload)
      ElMessage.success('风格已创建')
      router.push(`/styles/${created.id}`)
    } else if (editingStyle.value) {
      await store.editStyle(editingStyle.value.id, payload)
      ElMessage.success('风格已更新')
    }
    dialogOpen.value = false
  } finally {
    submitting.value = false
  }
}

async function handleDelete(id: string, name: string) {
  await ElMessageBox.confirm(`确认删除“${name}”？关联文章也会一并删除。`, '删除风格', {
    confirmButtonText: '删除',
    cancelButtonText: '取消',
    type: 'warning',
  })
  await store.removeStyle(id)
  ElMessage.success('风格已删除')
}
</script>
