from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.article import ArticleChunk
from app.services.embeddings import get_embeddings


def search_similar_chunks(
    db: Session,
    query: str,
    style_category_id: UUID,
    top_k: int = 5,
) -> list[tuple[ArticleChunk, float]]:
    query_embedding = get_embeddings([query])[0]
    embedding_literal = "[" + ",".join(str(x) for x in query_embedding) + "]"

    stmt = text("""
        SELECT id, 1 - (embedding <=> cast(:embedding AS vector)) AS similarity
        FROM article_chunks
        WHERE style_category_id = cast(:style_id AS uuid)
          AND embedding IS NOT NULL
        ORDER BY embedding <=> cast(:embedding AS vector)
        LIMIT :top_k
    """)

    rows = db.execute(stmt, {
        "embedding": embedding_literal,
        "style_id": str(style_category_id),
        "top_k": top_k,
    }).fetchall()

    if not rows:
        return []

    chunk_ids = [row[0] for row in rows]
    similarity_map = {row[0]: row[1] for row in rows}

    chunks = db.query(ArticleChunk).filter(ArticleChunk.id.in_(chunk_ids)).all()
    chunk_map = {chunk.id: chunk for chunk in chunks}

    results = []
    for cid in chunk_ids:
        if cid in chunk_map:
            results.append((chunk_map[cid], float(similarity_map[cid])))

    return results
