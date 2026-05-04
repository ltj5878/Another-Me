from uuid import UUID

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class GenerationTask(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "generation_tasks"

    style_category_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("style_categories.id", ondelete="CASCADE"))
    prompt: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(40), default="draft")

    style_category: Mapped["StyleCategory"] = relationship(back_populates="generation_tasks")
    outputs: Mapped[list["GeneratedOutput"]] = relationship(back_populates="generation_task", cascade="all, delete-orphan")


class GeneratedOutput(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "generated_outputs"

    generation_task_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("generation_tasks.id", ondelete="CASCADE"))
    content: Mapped[str] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict)

    generation_task: Mapped[GenerationTask] = relationship(back_populates="outputs")

