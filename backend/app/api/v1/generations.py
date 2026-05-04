from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.generation import GenerationCreate, GenerationDebugRun, GenerationRead, GenerationRevise
from app.services.generations import (
    create_generation,
    create_generation_stream,
    debug_run_generation,
    debug_run_generation_stream,
    delete_generation,
    get_generation,
    list_generations,
    revise_generation,
    revise_generation_stream,
)

router = APIRouter()


@router.post("", response_model=GenerationRead, status_code=status.HTTP_201_CREATED)
def create_generation_endpoint(payload: GenerationCreate, db: Session = Depends(get_db)) -> GenerationRead:
    return create_generation(db, payload)


@router.post("/stream")
def create_generation_stream_endpoint(payload: GenerationCreate, db: Session = Depends(get_db)) -> StreamingResponse:
    return _stream_response(create_generation_stream(db, payload))


@router.get("", response_model=list[GenerationRead])
def list_generations_endpoint(
    style_id: UUID | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[GenerationRead]:
    return list_generations(db, style_id=style_id, limit=limit)


@router.post("/debug-run", response_model=GenerationRead, status_code=status.HTTP_201_CREATED)
def debug_run_generation_endpoint(payload: GenerationDebugRun, db: Session = Depends(get_db)) -> GenerationRead:
    return debug_run_generation(db, payload)


@router.post("/debug-run/stream")
def debug_run_generation_stream_endpoint(payload: GenerationDebugRun, db: Session = Depends(get_db)) -> StreamingResponse:
    return _stream_response(debug_run_generation_stream(db, payload))


@router.post("/{generation_id}/revise", response_model=GenerationRead, status_code=status.HTTP_201_CREATED)
def revise_generation_endpoint(generation_id: UUID, payload: GenerationRevise, db: Session = Depends(get_db)) -> GenerationRead:
    return revise_generation(db, generation_id, payload)


@router.post("/{generation_id}/revise/stream")
def revise_generation_stream_endpoint(generation_id: UUID, payload: GenerationRevise, db: Session = Depends(get_db)) -> StreamingResponse:
    return _stream_response(revise_generation_stream(db, generation_id, payload))


@router.get("/{generation_id}", response_model=GenerationRead)
def get_generation_endpoint(generation_id: UUID, db: Session = Depends(get_db)) -> GenerationRead:
    return get_generation(db, generation_id)


@router.delete("/{generation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_generation_endpoint(generation_id: UUID, db: Session = Depends(get_db)) -> None:
    delete_generation(db, generation_id)


def _stream_response(iterator) -> StreamingResponse:
    return StreamingResponse(
        iterator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
