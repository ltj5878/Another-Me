from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


WRITING_TYPES = {"散文", "时评", "问答", "短评", "评论", "自定义"}
LENGTH_PRESETS = {"短", "中", "长", "自定义"}
IMITATION_STRENGTHS = {"轻微模仿", "中度模仿", "高度模仿"}
GENERATION_OPERATIONS = {
    "regenerate",
    "rewrite",
    "shorten",
    "expand",
    "sharper",
    "more_restrained",
    "more_like_style",
    "reduce_imitation_trace",
    "revise_opening",
    "revise_ending",
}


class GenerationCreate(BaseModel):
    style_category_id: UUID
    writing_type: str
    custom_writing_type: str | None = None
    user_input: str = Field(min_length=1, max_length=8000)
    length_preset: str
    custom_word_count: int | None = Field(default=None, ge=100, le=10000)
    imitation_strength: str
    include_references: bool = True
    extra_requirements: str | None = Field(default=None, max_length=4000)


class GenerationRevise(BaseModel):
    operation_type: str
    custom_instruction: str | None = Field(default=None, max_length=4000)
    include_references: bool = True


class GenerationDebugRun(BaseModel):
    style_category_id: UUID
    system_prompt: str = Field(min_length=1, max_length=20000)
    user_prompt: str = Field(min_length=1, max_length=60000)
    source_generation_id: UUID | None = None


class GeneratedOutputRead(BaseModel):
    id: UUID
    generation_task_id: UUID
    content: str
    metadata_json: dict
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class GenerationRead(BaseModel):
    id: UUID
    style_category_id: UUID
    prompt: str
    status: str
    created_at: datetime
    updated_at: datetime
    output: GeneratedOutputRead | None = None

    model_config = {"from_attributes": True}
