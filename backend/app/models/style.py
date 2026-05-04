from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class StyleCategory(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "style_categories"

    user_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)
    writing_type_hint: Mapped[str] = mapped_column(String(40), default="混合风格")

    user: Mapped["User | None"] = relationship(back_populates="style_categories")
    source_articles: Mapped[list["SourceArticle"]] = relationship(back_populates="style_category", cascade="all, delete-orphan")
    style_profile: Mapped["StyleProfile | None"] = relationship(back_populates="style_category", cascade="all, delete-orphan")
    generation_tasks: Mapped[list["GenerationTask"]] = relationship(back_populates="style_category", cascade="all, delete-orphan")


class StyleProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "style_profiles"

    style_category_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("style_categories.id", ondelete="CASCADE"),
        unique=True,
    )
    profile_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    summary: Mapped[str | None] = mapped_column(Text)
    sentence_style: Mapped[str | None] = mapped_column(Text)
    structure_style: Mapped[str | None] = mapped_column(Text)
    rhetoric_style: Mapped[str | None] = mapped_column(Text)
    imagery_style: Mapped[str | None] = mapped_column(Text)
    vocabulary_style: Mapped[str | None] = mapped_column(Text)
    tone_style: Mapped[str | None] = mapped_column(Text)
    argument_style: Mapped[str | None] = mapped_column(Text)
    opening_style: Mapped[str | None] = mapped_column(Text)
    ending_style: Mapped[str | None] = mapped_column(Text)
    do_rules: Mapped[str | None] = mapped_column(Text)
    dont_rules: Mapped[str | None] = mapped_column(Text)
    prompt_instruction: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1)

    style_category: Mapped[StyleCategory] = relationship(back_populates="style_profile")
