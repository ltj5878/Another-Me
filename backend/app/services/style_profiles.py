import json
import re
from uuid import UUID

from fastapi import HTTPException, status
from openai import OpenAI
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.models.article import SourceArticle
from app.models.style import StyleCategory, StyleProfile
from app.schemas.style_profile import PROFILE_FIELD_NAMES, StyleProfileStatusRead, StyleProfileUpdate

MIN_PROFILE_ARTICLES = 3
MAX_PROFILE_INPUT_CHARS = 24000


def get_profile_status(db: Session, style_id: UUID) -> StyleProfileStatusRead:
    style = db.get(StyleCategory, style_id)
    if style is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Style category not found")

    article_count = db.scalar(
        select(func.count(SourceArticle.id)).where(SourceArticle.style_category_id == style_id)
    ) or 0
    completed_article_count = db.scalar(
        select(func.count(SourceArticle.id)).where(
            SourceArticle.style_category_id == style_id,
            SourceArticle.status == "completed",
        )
    ) or 0
    latest_article_at = db.scalar(
        select(func.max(SourceArticle.created_at)).where(SourceArticle.style_category_id == style_id)
    )

    profile = style.style_profile
    is_stale = bool(profile and latest_article_at and latest_article_at > profile.updated_at)

    return StyleProfileStatusRead(
        style_category_id=style_id,
        article_count=article_count,
        completed_article_count=completed_article_count,
        minimum_required_articles=MIN_PROFILE_ARTICLES,
        can_generate=completed_article_count >= MIN_PROFILE_ARTICLES,
        is_stale=is_stale,
        latest_article_at=latest_article_at,
        profile=profile,
    )


def update_profile(db: Session, style_id: UUID, payload: StyleProfileUpdate) -> StyleProfileStatusRead:
    style = db.get(StyleCategory, style_id)
    if style is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Style category not found")

    profile = style.style_profile
    if profile is None:
        profile = StyleProfile(style_category_id=style.id, profile_json={}, version=1)
        db.add(profile)
        db.flush()

    updates = payload.model_dump(exclude_unset=True)
    for field_name, value in updates.items():
        if field_name in PROFILE_FIELD_NAMES:
            setattr(profile, field_name, value.strip() if isinstance(value, str) else value)

    profile.profile_json = {
        **(profile.profile_json or {}),
        "manual_edit": {field_name: getattr(profile, field_name) for field_name in PROFILE_FIELD_NAMES},
    }
    db.commit()
    db.refresh(style)
    return get_profile_status(db, style_id)


def generate_profile(db: Session, style_id: UUID) -> StyleProfileStatusRead:
    style = db.get(StyleCategory, style_id)
    if style is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Style category not found")
    if not settings.llm_api_key:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="LLM_API_KEY is not configured")

    articles = _load_completed_articles_with_chunks(db, style_id)
    if len(articles) < MIN_PROFILE_ARTICLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"At least {MIN_PROFILE_ARTICLES} completed articles are required to generate a style profile",
        )

    snippets = _build_representative_snippets(articles)
    if not snippets:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No completed article chunks are available")

    generated = _call_deepseek_for_profile(style, snippets)
    profile = style.style_profile
    if profile is None:
        profile = StyleProfile(style_category_id=style.id, profile_json={}, version=1)
        db.add(profile)
    else:
        profile.version += 1

    profile.profile_json = generated
    for field_name in PROFILE_FIELD_NAMES:
        setattr(profile, field_name, _coerce_profile_field(generated.get(field_name)))

    db.commit()
    return get_profile_status(db, style_id)


def _load_completed_articles_with_chunks(db: Session, style_id: UUID) -> list[SourceArticle]:
    return list(
        db.scalars(
            select(SourceArticle)
            .options(selectinload(SourceArticle.chunks))
            .where(SourceArticle.style_category_id == style_id, SourceArticle.status == "completed")
            .order_by(SourceArticle.created_at.desc())
        )
    )


def _build_representative_snippets(articles: list[SourceArticle]) -> str:
    blocks: list[str] = []
    total_chars = 0

    for article_index, article in enumerate(articles, start=1):
        chunks = sorted(article.chunks, key=lambda chunk: chunk.chunk_index)
        selected = _select_representative_chunks(chunks)
        if not selected:
            continue

        for chunk in selected:
            content = chunk.content.strip()
            if not content:
                continue
            if total_chars >= MAX_PROFILE_INPUT_CHARS:
                break
            remaining = MAX_PROFILE_INPUT_CHARS - total_chars
            clipped = content[:remaining]
            position = chunk.chunk_metadata.get("position", "unknown") if chunk.chunk_metadata else "unknown"
            blocks.append(
                f"【文章{article_index}｜{article.title}｜chunk#{chunk.chunk_index + 1}｜{position}】\n{clipped}"
            )
            total_chars += len(clipped)
        if total_chars >= MAX_PROFILE_INPUT_CHARS:
            break

    return "\n\n".join(blocks)


def _select_representative_chunks(chunks: list) -> list:
    if len(chunks) <= 3:
        return chunks

    selected_indexes = {0, len(chunks) // 2, len(chunks) - 1}
    return [chunks[index] for index in sorted(selected_indexes)]


def _call_deepseek_for_profile(style: StyleCategory, snippets: str) -> dict:
    client = OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)
    response = client.chat.completions.create(
        model=settings.llm_model,
        temperature=settings.llm_temperature,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "你是中文写作风格分析师。你只输出 JSON，不输出 Markdown。"
                    "你的任务是总结写作习惯，而不是复述文章内容。"
                ),
            },
            {
                "role": "user",
                "content": _build_profile_prompt(style, snippets),
            },
        ],
        stream=False,
    )
    content = response.choices[0].message.content or ""
    payload = _parse_json_object(content)
    missing = [field_name for field_name in PROFILE_FIELD_NAMES if field_name not in payload]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LLM response missing fields: {', '.join(missing)}",
        )
    return {field_name: _coerce_profile_field(payload.get(field_name)) for field_name in PROFILE_FIELD_NAMES}


def _build_profile_prompt(style: StyleCategory, snippets: str) -> str:
    fields = "\n".join(f'- "{field_name}": string' for field_name in PROFILE_FIELD_NAMES)
    return f"""
请分析下面这些同一风格分类下的代表性文章分块，生成一份可用于后续模仿写作的结构化风格画像。

风格名称：{style.name}
写作类型提示：{style.writing_type_hint}
风格描述：{style.description or "无"}

必须返回一个 JSON object，字段必须完整，且每个字段都是中文字符串：
{fields}

字段要求：
- summary：总体风格描述。
- sentence_style：句式特点。
- structure_style：段落结构和篇章推进方式。
- rhetoric_style：常用修辞。
- imagery_style：常用意象或场景材料。
- vocabulary_style：常用词汇、语气词、抽象词和连接词倾向。
- tone_style：情绪色彩和表达克制程度。
- argument_style：论证方式、判断方式、观点推进方式。
- opening_style：常见开头方式。
- ending_style：常见结尾方式。
- do_rules：后续模仿时应该遵守的事项。
- dont_rules：后续模仿时禁止或应该避免的事项。
- prompt_instruction：能直接放进后续写作生成系统提示词的模仿指令。

注意：
- 总结“表达方式”和“写作习惯”，不要复述文章情节。
- 不要编造作者经历。
- 禁止输出 JSON 之外的任何文字。

代表性分块：
{snippets}
""".strip()


def _parse_json_object(content: str) -> dict:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="LLM response is not valid JSON") from exc
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="LLM response must be a JSON object")
    return parsed


def _coerce_profile_field(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return "\n".join(str(item).strip() for item in value if str(item).strip())
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return str(value).strip()
