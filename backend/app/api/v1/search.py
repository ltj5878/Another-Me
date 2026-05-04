from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models.style import StyleCategory
from app.schemas.article import ArticleChunkRead, ChunkSearchRequest, ChunkSearchResult
from app.services.search import search_similar_chunks, smart_search_chunks

router = APIRouter()


@router.post("", response_model=list[ChunkSearchResult])
def search_chunks(
    payload: ChunkSearchRequest,
    db: Session = Depends(get_db),
) -> list[ChunkSearchResult]:
    if not settings.embedding_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Embedding service is not configured",
        )

    style = db.get(StyleCategory, payload.style_category_id)
    if style is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Style category not found",
        )

    if payload.rerank:
        results = smart_search_chunks(
            db=db,
            query=payload.query,
            style_category_id=payload.style_category_id,
            style_profile=style.style_profile,
            top_k=payload.top_k,
            candidate_k=payload.candidate_k,
        )
    else:
        results = search_similar_chunks(
            db=db,
            query=payload.query,
            style_category_id=payload.style_category_id,
            top_k=payload.top_k,
        )

    return [
        ChunkSearchResult(
            chunk=ArticleChunkRead.model_validate(chunk),
            similarity=round(sim, 4),
            style_score=getattr(item, "style_score", None),
            semantic_score=getattr(item, "semantic_score", None),
            rerank_reason=getattr(item, "rerank_reason", None),
            retrieval_strategy=getattr(item, "retrieval_strategy", None),
        )
        for item in results
        for chunk, sim in [item]
    ]
