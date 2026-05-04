from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class SourceArticleRead(BaseModel):
    id: UUID
    style_category_id: UUID
    title: str
    source_type: str
    original_filename: str
    word_count: int
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SourceArticleDetailRead(SourceArticleRead):
    raw_text: str
    cleaned_text: str
    chunks: list["ArticleChunkRead"] = []


class ArticleChunkRead(BaseModel):
    id: UUID
    source_article_id: UUID
    style_category_id: UUID
    chunk_index: int
    content: str
    token_count: int
    metadata: dict = Field(validation_alias="chunk_metadata")
    created_at: datetime

    model_config = {"from_attributes": True, "populate_by_name": True}


class ChunkSearchResult(BaseModel):
    chunk: ArticleChunkRead
    similarity: float


class ChunkSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=50)
    style_category_id: UUID
