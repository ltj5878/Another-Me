from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


WRITING_TYPE_HINTS = {"散文", "时评", "问答", "短评", "评论", "小说片段", "混合风格"}


class StyleCategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None
    writing_type_hint: str = "混合风格"


class StyleCategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None
    writing_type_hint: str | None = None


class StyleCategoryRead(BaseModel):
    id: UUID
    name: str
    description: str | None
    writing_type_hint: str
    article_count: int = 0
    last_article_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
