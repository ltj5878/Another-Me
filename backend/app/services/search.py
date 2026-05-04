from __future__ import annotations

from dataclasses import dataclass, field
import json
import re
from uuid import UUID

from openai import OpenAI
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.article import ArticleChunk
from app.models.style import StyleProfile
from app.schemas.style_profile import PROFILE_FIELD_NAMES
from app.services.embeddings import get_embeddings

SMART_RETRIEVAL_STRATEGY = "smart_rerank"
SEMANTIC_FALLBACK_STRATEGY = "semantic_fallback"
DISABLED_RETRIEVAL_STRATEGY = "disabled"


@dataclass
class RetrievedChunk:
    chunk: ArticleChunk
    similarity: float
    retrieval_strategy: str = SEMANTIC_FALLBACK_STRATEGY
    candidate_count: int = 0
    rerank_model: str | None = None
    style_score: float | None = None
    semantic_score: float | None = None
    rerank_reason: str | None = None
    rerank_metadata: dict = field(default_factory=dict)

    def __iter__(self):
        yield self.chunk
        yield self.similarity


def search_similar_chunks(
    db: Session,
    query: str,
    style_category_id: UUID,
    top_k: int = 5,
) -> list[RetrievedChunk]:
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

    results: list[RetrievedChunk] = []
    for cid in chunk_ids:
        if cid in chunk_map:
            results.append(RetrievedChunk(
                chunk=chunk_map[cid],
                similarity=float(similarity_map[cid]),
                retrieval_strategy=SEMANTIC_FALLBACK_STRATEGY,
                candidate_count=len(rows),
            ))

    return results


def smart_search_chunks(
    db: Session,
    query: str,
    style_category_id: UUID,
    style_profile: StyleProfile | None,
    top_k: int = 6,
    candidate_k: int = 20,
) -> list[RetrievedChunk]:
    candidates = search_similar_chunks(db, query=query, style_category_id=style_category_id, top_k=candidate_k)
    if not candidates:
        return []

    candidate_count = len(candidates)
    fallback = _semantic_fallback(candidates, top_k, candidate_count, "未执行 rerank")
    if not settings.llm_api_key:
        return _semantic_fallback(candidates, top_k, candidate_count, "LLM_API_KEY 未配置，已降级为语义检索")
    if style_profile is None:
        return _semantic_fallback(candidates, top_k, candidate_count, "风格画像不存在，已降级为语义检索")

    try:
        payload = _call_deepseek_for_rerank(query, style_profile, candidates, top_k)
        selected = _parse_rerank_selection(payload, candidates, top_k, candidate_count)
    except Exception as exc:
        return _semantic_fallback(candidates, top_k, candidate_count, f"rerank 失败，已降级为语义检索：{exc}")

    if not selected:
        return _semantic_fallback(candidates, top_k, candidate_count, "rerank 未返回有效片段，已降级为语义检索")
    return selected


def _semantic_fallback(candidates: list[RetrievedChunk], top_k: int, candidate_count: int, reason: str) -> list[RetrievedChunk]:
    selected = candidates[:top_k]
    for item in selected:
        item.retrieval_strategy = SEMANTIC_FALLBACK_STRATEGY
        item.candidate_count = candidate_count
        item.rerank_model = settings.llm_model if settings.llm_api_key else None
        item.style_score = None
        item.semantic_score = item.similarity
        item.rerank_reason = reason
        item.rerank_metadata = {"fallback_reason": reason}
    return selected


def _call_deepseek_for_rerank(query: str, profile: StyleProfile, candidates: list[RetrievedChunk], top_k: int) -> dict:
    client = OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)
    response = client.chat.completions.create(
        model=settings.llm_model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "你是中文写作风格检索重排器。你只输出 JSON。"
                    "你的任务不是续写文章，而是从候选片段中选择最适合作为风格 few-shot 示例的片段。"
                ),
            },
            {
                "role": "user",
                "content": _build_rerank_prompt(query, profile, candidates, top_k),
            },
        ],
        stream=False,
    )
    content = response.choices[0].message.content or ""
    return _parse_json_object(content)


def _build_rerank_prompt(query: str, profile: StyleProfile, candidates: list[RetrievedChunk], top_k: int) -> str:
    candidate_blocks = []
    for index, item in enumerate(candidates, start=1):
        chunk = item.chunk
        title = chunk.chunk_metadata.get("article_title", "未知文章") if chunk.chunk_metadata else "未知文章"
        position = chunk.chunk_metadata.get("position", "unknown") if chunk.chunk_metadata else "unknown"
        content = chunk.content.strip()[:1000]
        candidate_blocks.append(
            f"候选 {index}\n"
            f"id: {chunk.id}\n"
            f"语义相似度: {item.similarity:.4f}\n"
            f"文章: {title}\n"
            f"位置: {position}\n"
            f"内容:\n{content}"
        )

    return f"""
用户写作要求：
{query.strip()}

风格画像：
{_format_profile_for_rerank(profile)}

请从候选片段中选择最多 {top_k} 个最适合作为“模仿写法 few-shot 示例”的片段。

评分重点：
1. semantic_score：是否和用户题目、问题、语境相关。
2. style_score：是否体现风格画像里的句式、节奏、段落推进、修辞、语气和深度风格约束。
3. 优先选择有表达方式辨识度的片段，而不是只有情节信息或事实信息的片段。
4. 避免选择彼此高度重复的片段。
5. 片段只用于参考表达方式，不能要求后续直接复制。

必须返回 JSON object，格式如下：
{{
  "selected": [
    {{
      "candidate_index": 1,
      "style_score": 0.92,
      "semantic_score": 0.81,
      "reason": "这个片段体现了短句停顿和克制判断，且语境相关。"
    }}
  ]
}}

候选片段：
{chr(10).join(candidate_blocks)}
""".strip()


def _format_profile_for_rerank(profile: StyleProfile) -> str:
    labels = {
        "summary": "总体风格",
        "sentence_style": "句式特点",
        "structure_style": "段落结构",
        "rhetoric_style": "常用修辞",
        "imagery_style": "常用意象",
        "vocabulary_style": "常用词汇",
        "tone_style": "情绪色彩",
        "argument_style": "论证方式",
        "opening_style": "开头方式",
        "ending_style": "结尾方式",
        "do_rules": "必须遵守",
        "dont_rules": "禁止事项",
        "prompt_instruction": "模仿指令",
        "syntax_fingerprint": "句法指纹",
        "punctuation_fingerprint": "标点指纹",
        "preferred_words": "词汇偏好库",
        "structure_template": "结构模板",
        "style_constraints": "深度约束",
    }
    lines = []
    for field_name in PROFILE_FIELD_NAMES:
        value = (getattr(profile, field_name) or "").strip()
        if value:
            lines.append(f"{labels[field_name]}：{value}")
    return "\n".join(lines) or "未填写"


def _parse_rerank_selection(payload: dict, candidates: list[RetrievedChunk], top_k: int, candidate_count: int) -> list[RetrievedChunk]:
    selected_payload = payload.get("selected")
    if not isinstance(selected_payload, list):
        return []

    selected: list[RetrievedChunk] = []
    seen_indexes: set[int] = set()
    for item in selected_payload:
        if not isinstance(item, dict):
            continue
        candidate_index = _coerce_candidate_index(item.get("candidate_index"))
        if candidate_index is None or candidate_index in seen_indexes:
            continue
        if candidate_index < 1 or candidate_index > len(candidates):
            continue

        candidate = candidates[candidate_index - 1]
        seen_indexes.add(candidate_index)
        candidate.retrieval_strategy = SMART_RETRIEVAL_STRATEGY
        candidate.candidate_count = candidate_count
        candidate.rerank_model = settings.llm_model
        candidate.style_score = _coerce_score(item.get("style_score"))
        candidate.semantic_score = _coerce_score(item.get("semantic_score"))
        candidate.rerank_reason = _coerce_reason(item.get("reason"))
        candidate.rerank_metadata = {
            "candidate_index": candidate_index,
            "style_score": candidate.style_score,
            "semantic_score": candidate.semantic_score,
            "reason": candidate.rerank_reason,
        }
        selected.append(candidate)
        if len(selected) >= top_k:
            break

    return selected


def _parse_json_object(content: str) -> dict:
    text_value = content.strip()
    if text_value.startswith("```"):
        text_value = re.sub(r"^```(?:json)?\s*", "", text_value)
        text_value = re.sub(r"\s*```$", "", text_value)
    parsed = json.loads(text_value)
    if not isinstance(parsed, dict):
        raise ValueError("rerank response must be a JSON object")
    return parsed


def _coerce_candidate_index(value: object) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _coerce_score(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return max(0.0, min(1.0, float(value)))
    if isinstance(value, str):
        try:
            return max(0.0, min(1.0, float(value.strip())))
        except ValueError:
            return None
    return None


def _coerce_reason(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()[:500]
