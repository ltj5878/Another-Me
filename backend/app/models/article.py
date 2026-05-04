from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import Vector1536
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class SourceArticle(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "source_articles"

    style_category_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("style_categories.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(255))
    source_type: Mapped[str] = mapped_column(String(20), default="txt")
    original_filename: Mapped[str] = mapped_column(String(255))
    raw_text: Mapped[str] = mapped_column(Text)
    cleaned_text: Mapped[str] = mapped_column(Text)
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(40), default="completed")

    style_category: Mapped["StyleCategory"] = relationship(back_populates="source_articles")
    chunks: Mapped[list["ArticleChunk"]] = relationship(back_populates="source_article", cascade="all, delete-orphan")


class ArticleChunk(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "article_chunks"

    source_article_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("source_articles.id", ondelete="CASCADE"))
    style_category_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("style_categories.id", ondelete="CASCADE"))
    chunk_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    token_count: Mapped[int] = mapped_column(Integer, default=0)
    embedding: Mapped[list[float] | None] = mapped_column(Vector1536)
    chunk_metadata: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)

    source_article: Mapped[SourceArticle] = relationship(back_populates="chunks")
