from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


PROFILE_FIELD_NAMES = (
    "summary",
    "sentence_style",
    "structure_style",
    "rhetoric_style",
    "imagery_style",
    "vocabulary_style",
    "tone_style",
    "argument_style",
    "opening_style",
    "ending_style",
    "do_rules",
    "dont_rules",
    "prompt_instruction",
    "syntax_fingerprint",
    "punctuation_fingerprint",
    "preferred_words",
    "structure_template",
    "style_constraints",
)


class StyleProfileFields(BaseModel):
    summary: str | None = None
    sentence_style: str | None = None
    structure_style: str | None = None
    rhetoric_style: str | None = None
    imagery_style: str | None = None
    vocabulary_style: str | None = None
    tone_style: str | None = None
    argument_style: str | None = None
    opening_style: str | None = None
    ending_style: str | None = None
    do_rules: str | None = None
    dont_rules: str | None = None
    prompt_instruction: str | None = None
    syntax_fingerprint: str | None = None
    punctuation_fingerprint: str | None = None
    preferred_words: str | None = None
    structure_template: str | None = None
    style_constraints: str | None = None


class StyleProfileUpdate(StyleProfileFields):
    pass


class StyleProfileRead(StyleProfileFields):
    id: UUID
    style_category_id: UUID
    profile_json: dict
    version: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class StyleProfileMetricsRead(BaseModel):
    style_category_id: UUID
    metrics: dict


class StyleProfileStatusRead(BaseModel):
    style_category_id: UUID
    article_count: int
    completed_article_count: int
    minimum_required_articles: int
    can_generate: bool
    is_stale: bool
    latest_article_at: datetime | None
    profile: StyleProfileRead | None
