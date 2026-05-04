from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.models.article import SourceArticle
from app.models.style import StyleCategory
from app.schemas.article import SourceArticleDetailRead, SourceArticleRead
from app.schemas.style import WRITING_TYPE_HINTS, StyleCategoryCreate, StyleCategoryRead, StyleCategoryUpdate
from app.schemas.style_profile import StyleProfileMetricsRead, StyleProfileStatusRead, StyleProfileUpdate
from app.services.articles import process_source_article, upload_source_article
from app.services.style_profiles import get_profile_metrics, get_profile_status, start_profile_generation, update_profile

router = APIRouter()


def _style_read(row: tuple[StyleCategory, int, object]) -> StyleCategoryRead:
    style, article_count, last_article_at = row
    return StyleCategoryRead(
        id=style.id,
        name=style.name,
        description=style.description,
        writing_type_hint=style.writing_type_hint,
        article_count=article_count,
        last_article_at=last_article_at,
        created_at=style.created_at,
        updated_at=style.updated_at,
    )


def _styles_query() -> Select[tuple[StyleCategory, int, object]]:
    return (
        select(
            StyleCategory,
            func.count(SourceArticle.id).label("article_count"),
            func.max(SourceArticle.created_at).label("last_article_at"),
        )
        .outerjoin(SourceArticle, SourceArticle.style_category_id == StyleCategory.id)
        .group_by(StyleCategory.id)
        .order_by(StyleCategory.created_at.desc())
    )


@router.get("", response_model=list[StyleCategoryRead])
def list_styles(db: Session = Depends(get_db)) -> list[StyleCategoryRead]:
    rows = db.execute(_styles_query()).all()
    return [_style_read(row) for row in rows]


@router.post("", response_model=StyleCategoryRead, status_code=status.HTTP_201_CREATED)
def create_style(payload: StyleCategoryCreate, db: Session = Depends(get_db)) -> StyleCategoryRead:
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Style name is required")
    writing_type_hint = payload.writing_type_hint.strip()
    if writing_type_hint not in WRITING_TYPE_HINTS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported writing type hint")
    description = payload.description.strip() if payload.description else None
    style = StyleCategory(name=name, description=description or None, writing_type_hint=writing_type_hint)
    db.add(style)
    db.commit()
    db.refresh(style)
    return _style_read((style, 0, None))


@router.get("/{style_id}", response_model=StyleCategoryRead)
def get_style(style_id: UUID, db: Session = Depends(get_db)) -> StyleCategoryRead:
    row = db.execute(_styles_query().where(StyleCategory.id == style_id)).one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Style category not found")
    return _style_read(row)


@router.patch("/{style_id}", response_model=StyleCategoryRead)
def update_style(style_id: UUID, payload: StyleCategoryUpdate, db: Session = Depends(get_db)) -> StyleCategoryRead:
    style = db.get(StyleCategory, style_id)
    if style is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Style category not found")

    if payload.name is not None:
        name = payload.name.strip()
        if not name:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Style name is required")
        style.name = name

    if payload.description is not None:
        description = payload.description.strip()
        style.description = description or None

    if payload.writing_type_hint is not None:
        writing_type_hint = payload.writing_type_hint.strip()
        if writing_type_hint not in WRITING_TYPE_HINTS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported writing type hint")
        style.writing_type_hint = writing_type_hint

    db.commit()
    row = db.execute(_styles_query().where(StyleCategory.id == style_id)).one()
    return _style_read(row)


@router.delete("/{style_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_style(style_id: UUID, db: Session = Depends(get_db)) -> None:
    style = db.get(StyleCategory, style_id)
    if style is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Style category not found")
    db.delete(style)
    db.commit()


@router.get("/{style_id}/profile", response_model=StyleProfileStatusRead)
def get_style_profile(style_id: UUID, db: Session = Depends(get_db)) -> StyleProfileStatusRead:
    return get_profile_status(db, style_id)


@router.get("/{style_id}/profile/metrics", response_model=StyleProfileMetricsRead)
def get_style_profile_metrics(style_id: UUID, db: Session = Depends(get_db)) -> StyleProfileMetricsRead:
    return get_profile_metrics(db, style_id)


@router.post("/{style_id}/profile/generate", response_model=StyleProfileStatusRead)
def generate_style_profile(
    style_id: UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> StyleProfileStatusRead:
    result = start_profile_generation(db, style_id)
    background_tasks.add_task(start_profile_generation_background, style_id)
    return result


@router.patch("/{style_id}/profile", response_model=StyleProfileStatusRead)
def patch_style_profile(
    style_id: UUID,
    payload: StyleProfileUpdate,
    db: Session = Depends(get_db),
) -> StyleProfileStatusRead:
    return update_profile(db, style_id, payload)


@router.get("/{style_id}/articles", response_model=list[SourceArticleRead])
def list_articles(style_id: UUID, db: Session = Depends(get_db)) -> list[SourceArticle]:
    if db.get(StyleCategory, style_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Style category not found")
    return list(
        db.scalars(
            select(SourceArticle)
            .where(SourceArticle.style_category_id == style_id)
            .order_by(SourceArticle.created_at.desc())
        )
    )


@router.get("/{style_id}/articles/{article_id}", response_model=SourceArticleDetailRead)
def get_article(style_id: UUID, article_id: UUID, db: Session = Depends(get_db)) -> SourceArticle:
    article = db.scalar(
        select(SourceArticle)
        .options(selectinload(SourceArticle.chunks))
        .where(SourceArticle.id == article_id)
    )
    if article is None or article.style_category_id != style_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found")
    article.chunks.sort(key=lambda chunk: chunk.chunk_index)
    return article


@router.delete("/{style_id}/articles/{article_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_article(style_id: UUID, article_id: UUID, db: Session = Depends(get_db)) -> None:
    article = db.get(SourceArticle, article_id)
    if article is None or article.style_category_id != style_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found")
    
    db.delete(article)
    db.commit()


@router.post("/{style_id}/articles/upload", response_model=SourceArticleRead, status_code=status.HTTP_201_CREATED)
def upload_article(
    style_id: UUID,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> SourceArticle:
    article = upload_source_article(db, style_id, file)
    background_tasks.add_task(process_source_article, article.id)
    return article


def start_profile_generation_background(style_id: UUID) -> None:
    from app.services.style_profiles import run_profile_generation_background

    run_profile_generation_background(style_id)
