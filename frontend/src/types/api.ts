export interface StyleCategory {
  id: string
  name: string
  description: string | null
  writing_type_hint: string
  article_count: number
  last_article_at: string | null
  created_at: string
  updated_at: string
}

export interface StyleCreatePayload {
  name: string
  description?: string
  writing_type_hint: string
}

export type StyleUpdatePayload = Partial<StyleCreatePayload>

export interface SourceArticle {
  id: string
  style_category_id: string
  title: string
  source_type: string
  original_filename: string
  word_count: number
  status: string
  created_at: string
  updated_at: string
}

export interface SourceArticleDetail extends SourceArticle {
  raw_text: string
  cleaned_text: string
  chunks: ArticleChunk[]
}

export interface ArticleChunk {
  id: string
  source_article_id: string
  style_category_id: string
  chunk_index: number
  content: string
  token_count: number
  metadata: Record<string, unknown>
  created_at: string
}

export interface StyleProfile {
  id: string
  style_category_id: string
  profile_json: Record<string, unknown>
  summary: string | null
  sentence_style: string | null
  structure_style: string | null
  rhetoric_style: string | null
  imagery_style: string | null
  vocabulary_style: string | null
  tone_style: string | null
  argument_style: string | null
  opening_style: string | null
  ending_style: string | null
  do_rules: string | null
  dont_rules: string | null
  prompt_instruction: string | null
  version: number
  created_at: string
  updated_at: string
}

export interface StyleProfileStatus {
  style_category_id: string
  article_count: number
  completed_article_count: number
  minimum_required_articles: number
  can_generate: boolean
  is_stale: boolean
  latest_article_at: string | null
  profile: StyleProfile | null
}

export type StyleProfilePayload = Partial<
  Pick<
    StyleProfile,
    | 'summary'
    | 'sentence_style'
    | 'structure_style'
    | 'rhetoric_style'
    | 'imagery_style'
    | 'vocabulary_style'
    | 'tone_style'
    | 'argument_style'
    | 'opening_style'
    | 'ending_style'
    | 'do_rules'
    | 'dont_rules'
    | 'prompt_instruction'
  >
>

export interface GenerationCreatePayload {
  style_category_id: string
  writing_type: string
  custom_writing_type?: string | null
  user_input: string
  length_preset: string
  custom_word_count?: number | null
  imitation_strength: string
  include_references: boolean
  extra_requirements?: string | null
}

export interface GenerationRevisePayload {
  operation_type: string
  custom_instruction?: string | null
  include_references: boolean
}

export interface GenerationDebugRunPayload {
  style_category_id: string
  system_prompt: string
  user_prompt: string
  source_generation_id?: string | null
}

export interface GeneratedOutput {
  id: string
  generation_task_id: string
  content: string
  metadata_json: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface Generation {
  id: string
  style_category_id: string
  prompt: string
  status: string
  created_at: string
  updated_at: string
  output: GeneratedOutput | null
}

export const WRITING_TYPE_OPTIONS = ['散文', '时评', '问答', '短评', '评论', '小说片段', '混合风格'] as const
