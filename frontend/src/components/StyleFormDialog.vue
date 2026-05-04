<template>
  <el-dialog :model-value="modelValue" :title="title" width="500px" @close="emit('update:modelValue', false)">
    <el-form :model="form" label-position="top" @submit.prevent>
      <el-form-item label="风格名称" required>
        <el-input v-model="form.name" placeholder="例如：个人散文" maxlength="120" show-word-limit />
      </el-form-item>
      <el-form-item label="写作类型">
        <el-select v-model="form.writing_type_hint" placeholder="请选择写作类型">
          <el-option v-for="option in WRITING_TYPE_OPTIONS" :key="option" :label="option" :value="option" />
        </el-select>
      </el-form-item>
      <el-form-item label="描述">
        <el-input v-model="form.description" type="textarea" :rows="4" placeholder="这个风格的使用场景或语言倾向" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" :loading="saving" @click="handleSubmit">{{ submitLabel }}</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { computed, reactive, watch } from 'vue'

import type { StyleCategory, StyleCreatePayload } from '@/types/api'
import { WRITING_TYPE_OPTIONS } from '@/types/api'

const props = defineProps<{
  modelValue: boolean
  mode: 'create' | 'edit'
  style?: StyleCategory | null
  saving?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  submit: [payload: StyleCreatePayload]
}>()

const form = reactive<StyleCreatePayload>({
  name: '',
  description: '',
  writing_type_hint: '混合风格',
})

const title = computed(() => (props.mode === 'create' ? '新建风格' : '编辑风格'))
const submitLabel = computed(() => (props.mode === 'create' ? '创建' : '保存'))

watch(
  () => props.modelValue,
  (open) => {
    if (!open) return
    form.name = props.style?.name ?? ''
    form.description = props.style?.description ?? ''
    form.writing_type_hint = props.style?.writing_type_hint ?? '混合风格'
  },
  { immediate: true },
)

function handleSubmit() {
  if (!form.name.trim()) {
    ElMessage.warning('请填写风格名称')
    return
  }

  emit('submit', {
    name: form.name.trim(),
    description: form.description?.trim() || undefined,
    writing_type_hint: form.writing_type_hint,
  })
}
</script>
