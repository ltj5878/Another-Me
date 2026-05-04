import json
from collections.abc import Iterator
from queue import SimpleQueue
from threading import Thread
from uuid import UUID

from fastapi import HTTPException, status
from openai import OpenAI
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.generation import GeneratedOutput, GenerationTask
from app.models.style import StyleCategory, StyleProfile
from app.schemas.generation import (
    GENERATION_OPERATIONS,
    IMITATION_STRENGTHS,
    LENGTH_PRESETS,
    WRITING_TYPES,
    GenerationCreate,
    GenerationDebugRun,
    GenerationRead,
    GenerationRevise,
)
from app.schemas.style_profile import PROFILE_FIELD_NAMES
from app.services.search import DISABLED_RETRIEVAL_STRATEGY, smart_search_chunks

REFERENCE_CHUNK_COUNT = 6
REFERENCE_CANDIDATE_COUNT = 20
GENERATION_REASONING_EFFORT = "max"
OPERATION_LABELS = {
    "initial": "初次生成",
    "regenerate": "重新生成",
    "rewrite": "继续改写",
    "shorten": "缩短",
    "expand": "扩写",
    "sharper": "更尖锐",
    "more_restrained": "更克制",
    "more_like_style": "更像原风格",
    "reduce_imitation_trace": "降低模仿痕迹",
    "revise_opening": "修改开头",
    "revise_ending": "修改结尾",
    "debug_prompt": "Prompt 调试",
}
OPERATION_INSTRUCTIONS = {
    "rewrite": "根据用户自由指令修改当前正文。",
    "shorten": "压缩篇幅，保留核心情绪、结构和风格。",
    "expand": "增加细节、场景和节奏层次，不改变核心意思。",
    "sharper": "增强判断力度、冲突感和表达锋利度。",
    "more_restrained": "降低直白表达，减少情绪宣泄，保留余味。",
    "more_like_style": "更严格贴合风格画像的句式、节奏、意象和结尾方式。",
    "reduce_imitation_trace": "保留整体气质，但减少刻意复刻、旧文近似表达和过强风格标签。",
    "revise_opening": "只重写开头部分，并自然衔接后文。",
    "revise_ending": "只重写结尾部分，增强收束和余味。",
}


def create_generation(db: Session, payload: GenerationCreate) -> GenerationRead:
    _validate_generation_payload(payload)

    style = _get_style_with_profile(db, payload.style_category_id)
    _ensure_llm_configured()
    references = _maybe_search_references(db, payload.include_references, _generation_search_query(payload), payload.style_category_id, style.style_profile)

    system_prompt = _build_system_prompt()
    user_prompt = _build_user_prompt(style, style.style_profile, payload, references)
    final_prompt = f"【System Prompt】\n{system_prompt}\n\n【User Prompt】\n{user_prompt}"
    metadata = _build_metadata(payload, style.style_profile, references, system_prompt, user_prompt, operation_type="initial")

    return _run_and_save_generation(db, style.id, final_prompt, system_prompt, user_prompt, metadata)


def revise_generation(db: Session, generation_id: UUID, payload: GenerationRevise) -> GenerationRead:
    if payload.operation_type not in GENERATION_OPERATIONS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不支持的修改操作")

    source_task = _get_generation_task(db, generation_id)
    source_output = _latest_output(source_task)
    if source_task.status != "completed" or source_output is None or not source_output.content.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前生成记录没有可修改的正文")

    _ensure_llm_configured()
    style = _get_style_with_profile(db, source_task.style_category_id)
    source_metadata = source_output.metadata_json or {}
    references = _maybe_search_references(
        db,
        payload.include_references,
        str(source_metadata.get("user_input") or source_output.content[:1200]),
        source_task.style_category_id,
        style.style_profile,
    )

    if payload.operation_type == "regenerate":
        generation_payload = _payload_from_source_metadata(source_task, source_metadata)
        system_prompt = _build_system_prompt()
        user_prompt = _build_user_prompt(style, style.style_profile, generation_payload, references)
    else:
        system_prompt = _build_revision_system_prompt()
        user_prompt = _build_revision_user_prompt(style, style.style_profile, source_output.content, payload, references)

    final_prompt = f"【System Prompt】\n{system_prompt}\n\n【User Prompt】\n{user_prompt}"
    metadata = _build_revision_metadata(
        payload,
        style.style_profile,
        references,
        system_prompt,
        user_prompt,
        source_task,
        source_output,
        source_metadata,
    )
    return _run_and_save_generation(db, style.id, final_prompt, system_prompt, user_prompt, metadata)


def debug_run_generation(db: Session, payload: GenerationDebugRun) -> GenerationRead:
    style = db.get(StyleCategory, payload.style_category_id)
    if style is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="风格分类不存在")
    _ensure_llm_configured()

    source_task = _get_generation_task(db, payload.source_generation_id) if payload.source_generation_id else None
    source_output = _latest_output(source_task) if source_task else None
    source_metadata = source_output.metadata_json if source_output else {}
    metadata = {
        "operation_type": "debug_prompt",
        "operation_label": OPERATION_LABELS["debug_prompt"],
        "source_generation_id": str(source_task.id) if source_task else None,
        "source_output_id": str(source_output.id) if source_output else None,
        "display_title": _build_display_title(source_metadata or {}, OPERATION_LABELS["debug_prompt"]),
        "debug_prompt_modified": True,
        "system_prompt": payload.system_prompt,
        "user_prompt": payload.user_prompt,
        "retrieved_chunks": list((source_metadata or {}).get("retrieved_chunks") or []),
        "style_profile_snapshot": dict((source_metadata or {}).get("style_profile_snapshot") or {}),
        "model": settings.llm_model,
        "reasoning_effort": GENERATION_REASONING_EFFORT,
        "thinking": {"type": "enabled"},
    }
    final_prompt = f"【System Prompt】\n{payload.system_prompt}\n\n【User Prompt】\n{payload.user_prompt}"
    return _run_and_save_generation(db, style.id, final_prompt, payload.system_prompt, payload.user_prompt, metadata)


def create_generation_stream(db: Session, payload: GenerationCreate) -> Iterator[str]:
    try:
        _validate_generation_payload(payload)
        style = _get_style_with_profile(db, payload.style_category_id)
        _ensure_llm_configured()
        references = _maybe_search_references(db, payload.include_references, _generation_search_query(payload), payload.style_category_id, style.style_profile)
        system_prompt = _build_system_prompt()
        user_prompt = _build_user_prompt(style, style.style_profile, payload, references)
        final_prompt = f"【System Prompt】\n{system_prompt}\n\n【User Prompt】\n{user_prompt}"
        metadata = _build_metadata(payload, style.style_profile, references, system_prompt, user_prompt, operation_type="initial")
        yield from _run_and_stream_generation(db, style.id, final_prompt, system_prompt, user_prompt, metadata)
    except Exception as exc:
        yield _sse_event("error", {"detail": _stream_error_message(exc)})


def revise_generation_stream(db: Session, generation_id: UUID, payload: GenerationRevise) -> Iterator[str]:
    try:
        if payload.operation_type not in GENERATION_OPERATIONS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不支持的修改操作")
        source_task = _get_generation_task(db, generation_id)
        source_output = _latest_output(source_task)
        if source_task.status != "completed" or source_output is None or not source_output.content.strip():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前生成记录没有可修改的正文")

        _ensure_llm_configured()
        style = _get_style_with_profile(db, source_task.style_category_id)
        source_metadata = source_output.metadata_json or {}
        references = _maybe_search_references(
            db,
            payload.include_references,
            str(source_metadata.get("user_input") or source_output.content[:1200]),
            source_task.style_category_id,
            style.style_profile,
        )

        if payload.operation_type == "regenerate":
            generation_payload = _payload_from_source_metadata(source_task, source_metadata)
            system_prompt = _build_system_prompt()
            user_prompt = _build_user_prompt(style, style.style_profile, generation_payload, references)
        else:
            system_prompt = _build_revision_system_prompt()
            user_prompt = _build_revision_user_prompt(style, style.style_profile, source_output.content, payload, references)

        final_prompt = f"【System Prompt】\n{system_prompt}\n\n【User Prompt】\n{user_prompt}"
        metadata = _build_revision_metadata(
            payload,
            style.style_profile,
            references,
            system_prompt,
            user_prompt,
            source_task,
            source_output,
            source_metadata,
        )
        yield from _run_and_stream_generation(db, style.id, final_prompt, system_prompt, user_prompt, metadata)
    except Exception as exc:
        yield _sse_event("error", {"detail": _stream_error_message(exc)})


def debug_run_generation_stream(db: Session, payload: GenerationDebugRun) -> Iterator[str]:
    try:
        style = db.get(StyleCategory, payload.style_category_id)
        if style is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="风格分类不存在")
        _ensure_llm_configured()

        source_task = _get_generation_task(db, payload.source_generation_id) if payload.source_generation_id else None
        source_output = _latest_output(source_task) if source_task else None
        source_metadata = source_output.metadata_json if source_output else {}
        metadata = {
            "operation_type": "debug_prompt",
            "operation_label": OPERATION_LABELS["debug_prompt"],
            "source_generation_id": str(source_task.id) if source_task else None,
            "source_output_id": str(source_output.id) if source_output else None,
            "display_title": _build_display_title(source_metadata or {}, OPERATION_LABELS["debug_prompt"]),
            "debug_prompt_modified": True,
            "system_prompt": payload.system_prompt,
            "user_prompt": payload.user_prompt,
            "retrieved_chunks": list((source_metadata or {}).get("retrieved_chunks") or []),
            "style_profile_snapshot": dict((source_metadata or {}).get("style_profile_snapshot") or {}),
            "model": settings.llm_model,
            "reasoning_effort": GENERATION_REASONING_EFFORT,
            "thinking": {"type": "enabled"},
        }
        final_prompt = f"【System Prompt】\n{payload.system_prompt}\n\n【User Prompt】\n{payload.user_prompt}"
        yield from _run_and_stream_generation(db, style.id, final_prompt, payload.system_prompt, payload.user_prompt, metadata)
    except Exception as exc:
        yield _sse_event("error", {"detail": _stream_error_message(exc)})


def list_generations(
    db: Session,
    style_id: UUID | None = None,
    limit: int = 20,
) -> list[GenerationRead]:
    limit = max(1, min(limit, 100))
    stmt = (
        select(GenerationTask)
        .options(selectinload(GenerationTask.outputs))
        .order_by(GenerationTask.created_at.desc())
        .limit(limit)
    )
    if style_id is not None:
        stmt = stmt.where(GenerationTask.style_category_id == style_id)
    tasks = list(db.scalars(stmt))
    return [_to_generation_read(task) for task in tasks]


def get_generation(db: Session, generation_id: UUID) -> GenerationRead:
    task = _get_generation_task(db, generation_id)
    return _to_generation_read(task)


def delete_generation(db: Session, generation_id: UUID) -> None:
    task = db.get(GenerationTask, generation_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="生成记录不存在")
    db.delete(task)
    db.commit()


def _get_generation_task(db: Session, generation_id: UUID) -> GenerationTask:
    task = db.scalar(
        select(GenerationTask)
        .options(selectinload(GenerationTask.outputs))
        .where(GenerationTask.id == generation_id)
    )
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="生成记录不存在")
    return task


def _get_style_with_profile(db: Session, style_id: UUID) -> StyleCategory:
    style = db.scalar(
        select(StyleCategory)
        .options(selectinload(StyleCategory.style_profile))
        .where(StyleCategory.id == style_id)
    )
    if style is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="风格分类不存在")
    if style.style_profile is None or not _has_profile_content(style.style_profile):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前风格还没有风格画像，请先生成或手动编辑画像")
    return style


def _ensure_llm_configured() -> None:
    if not settings.llm_api_key:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="LLM_API_KEY 未配置")


def _maybe_search_references(
    db: Session,
    include_references: bool,
    query: str,
    style_id: UUID,
    profile: StyleProfile | None,
) -> list:
    if not include_references:
        return []
    try:
        return smart_search_chunks(
            db,
            query=query,
            style_category_id=style_id,
            style_profile=profile,
            top_k=REFERENCE_CHUNK_COUNT,
            candidate_k=REFERENCE_CANDIDATE_COUNT,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"检索参考片段失败：{exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"检索参考片段失败：{exc}") from exc


def _run_and_save_generation(
    db: Session,
    style_id: UUID,
    final_prompt: str,
    system_prompt: str,
    user_prompt: str,
    metadata: dict,
) -> GenerationRead:
    task = GenerationTask(style_category_id=style_id, prompt=final_prompt, status="running")
    db.add(task)
    db.commit()
    db.refresh(task)

    try:
        content = _call_deepseek(system_prompt, user_prompt)
    except Exception as exc:
        task.status = "failed"
        db.add(
            GeneratedOutput(
                generation_task_id=task.id,
                content="",
                metadata_json={**metadata, "error": str(exc)},
            )
        )
        db.commit()
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"文章生成失败：{exc}") from exc

    task.status = "completed"
    db.add(GeneratedOutput(generation_task_id=task.id, content=content, metadata_json=metadata))
    db.commit()
    return get_generation(db, task.id)


def _run_and_stream_generation(
    db: Session,
    style_id: UUID,
    final_prompt: str,
    system_prompt: str,
    user_prompt: str,
    metadata: dict,
) -> Iterator[str]:
    task = GenerationTask(style_category_id=style_id, prompt=final_prompt, status="running")
    db.add(task)
    db.commit()
    db.refresh(task)

    events: SimpleQueue[tuple[str, dict] | None] = SimpleQueue()
    worker = Thread(
        target=_stream_generation_worker,
        args=(task.id, system_prompt, user_prompt, metadata, events),
        daemon=True,
    )
    worker.start()

    yield _sse_event("started", {
        "generation_id": str(task.id),
        "style_category_id": str(style_id),
        "metadata": metadata,
    })

    while True:
        item = events.get()
        if item is None:
            break
        event, data = item
        yield _sse_event(event, data)


def _stream_generation_worker(
    task_id: UUID,
    system_prompt: str,
    user_prompt: str,
    metadata: dict,
    events: SimpleQueue[tuple[str, dict] | None],
) -> None:
    content_parts: list[str] = []
    thinking_emitted = False
    try:
        for event_type, text in _call_deepseek_stream(system_prompt, user_prompt):
            if event_type == "progress" and not thinking_emitted:
                thinking_emitted = True
                events.put(("progress", {"detail": "DeepSeek 正在思考，正文开始生成后会实时显示..."}))
                continue
            if event_type != "delta" or not text:
                continue
            content_parts.append(text)
            events.put(("delta", {"content": text}))
    except Exception as exc:
        _save_stream_failure(task_id, metadata, str(exc))
        events.put(("error", {"generation_id": str(task_id), "detail": f"文章生成失败：{exc}"}))
        events.put(None)
        return

    content = "".join(content_parts).strip()
    if not content:
        _save_stream_failure(task_id, metadata, "DeepSeek 没有返回正文")
        events.put(("error", {"generation_id": str(task_id), "detail": "文章生成失败：DeepSeek 没有返回正文"}))
        events.put(None)
        return

    with SessionLocal() as worker_db:
        task = worker_db.get(GenerationTask, task_id)
        if task is None:
            events.put(("error", {"generation_id": str(task_id), "detail": "生成任务不存在"}))
            events.put(None)
            return
        task.status = "completed"
        worker_db.add(GeneratedOutput(generation_task_id=task.id, content=content, metadata_json=metadata))
        worker_db.commit()
        completed = get_generation(worker_db, task.id)
    events.put(("completed", completed.model_dump(mode="json")))
    events.put(None)


def _save_stream_failure(task_id: UUID, metadata: dict, error: str) -> None:
    with SessionLocal() as worker_db:
        task = worker_db.get(GenerationTask, task_id)
        if task is None:
            return
        task.status = "failed"
        worker_db.add(GeneratedOutput(generation_task_id=task.id, content="", metadata_json={**metadata, "error": error}))
        worker_db.commit()


def _latest_output(task: GenerationTask | None) -> GeneratedOutput | None:
    if task is None or not task.outputs:
        return None
    return sorted(task.outputs, key=lambda output: output.created_at, reverse=True)[0]


def _validate_generation_payload(payload: GenerationCreate) -> None:
    if payload.writing_type not in WRITING_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不支持的写作类型")
    if payload.writing_type == "自定义" and not (payload.custom_writing_type or "").strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请填写自定义写作类型")
    if payload.length_preset not in LENGTH_PRESETS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不支持的文章长度")
    if payload.length_preset == "自定义" and payload.custom_word_count is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请填写自定义字数")
    if payload.imitation_strength not in IMITATION_STRENGTHS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不支持的语气强度")


def _has_profile_content(profile: StyleProfile) -> bool:
    return any((getattr(profile, field_name) or "").strip() for field_name in PROFILE_FIELD_NAMES)


def _generation_search_query(payload: GenerationCreate) -> str:
    return "\n".join(
        part
        for part in [
            payload.user_input.strip(),
            payload.extra_requirements.strip() if payload.extra_requirements else "",
            payload.custom_writing_type.strip() if payload.writing_type == "自定义" and payload.custom_writing_type else "",
        ]
        if part
    )


def _build_system_prompt() -> str:
    return (
        "你是一个中文写作助手，任务是根据指定风格生成文章。"
        "你必须根据风格画像中的句式、节奏、结构、修辞和语气完成自然、完整、可发表的正文。"
        "不要说明自己在模仿，不要直接复制参考片段，不要使用模板化 AI 语言。"
        "只输出正文，不输出标题解释、创作说明或分析过程。"
    )


def _build_revision_system_prompt() -> str:
    return (
        "你是一个中文写作编辑。你的任务是在保留原文核心内容和指定风格的前提下，"
        "根据用户给出的修改操作改写当前正文。不要解释修改过程，不要输出修改说明，只输出修改后的正文。"
    )


def _build_user_prompt(
    style: StyleCategory,
    profile: StyleProfile,
    payload: GenerationCreate,
    references: list,
) -> str:
    writing_type = payload.custom_writing_type.strip() if payload.writing_type == "自定义" and payload.custom_writing_type else payload.writing_type
    reference_text = _format_references(references) if payload.include_references else "本次不引用旧文片段。"
    return f"""
【风格名称】
{style.name}

【风格画像】
{_format_style_profile(profile)}

【深度风格约束】
{_format_deep_style_constraints(profile)}

【参考片段】
{reference_text}

【用户要求】
{payload.user_input.strip()}

【写作类型】
{writing_type}

【文章长度】
{_format_length(payload)}

【语气强度】
{payload.imitation_strength}：{_imitation_instruction(payload.imitation_strength)}

【补充要求】
{payload.extra_requirements.strip() if payload.extra_requirements else "无"}

【生成要求】
1. 模仿风格画像中的句式、节奏、结构、修辞和语气。
2. 句长、标点、偏好词和篇章结构参考“深度风格约束”，但不要机械堆砌。
3. 不要直接复制参考片段，也不要改写成近似原句。
4. 不要说明自己在模仿。
5. 不要使用模板化 AI 语言。
6. 保持自然、完整、可发表。
7. 只输出正文。
""".strip()


def _build_revision_user_prompt(
    style: StyleCategory,
    profile: StyleProfile,
    source_text: str,
    payload: GenerationRevise,
    references: list,
) -> str:
    operation_label = OPERATION_LABELS[payload.operation_type]
    operation_instruction = OPERATION_INSTRUCTIONS[payload.operation_type]
    custom_instruction = payload.custom_instruction.strip() if payload.custom_instruction else "无"
    reference_text = _format_references(references) if payload.include_references else "本次不引用旧文片段。"
    return f"""
【风格名称】
{style.name}

【风格画像】
{_format_style_profile(profile)}

【深度风格约束】
{_format_deep_style_constraints(profile)}

【参考片段】
{reference_text}

【当前正文】
{source_text.strip()}

【修改操作】
{operation_label}：{operation_instruction}

【用户补充修改指令】
{custom_instruction}

【改写要求】
1. 基于当前正文继续修改，不要另起炉灶，除非操作是“重新生成”。
2. 保留风格画像中的句式、节奏、结构、修辞和语气。
3. 参考“深度风格约束”调整句长、标点、偏好词和结构，不要机械复刻。
4. 不要直接复制参考片段，也不要改写成近似原句。
5. 不要说明自己在模仿或正在修改。
6. 只输出修改后的正文。
""".strip()


def _format_style_profile(profile: StyleProfile) -> str:
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


def _format_deep_style_constraints(profile: StyleProfile) -> str:
    lines = []
    fields = [
        ("syntax_fingerprint", "句法指纹"),
        ("punctuation_fingerprint", "标点习惯"),
        ("preferred_words", "词汇偏好库"),
        ("structure_template", "结构模板"),
        ("style_constraints", "风格约束"),
    ]
    for field_name, label in fields:
        value = (getattr(profile, field_name) or "").strip()
        if value:
            lines.append(f"{label}：{value}")
    if not lines:
        return "暂无深度画像约束；仅使用基础风格画像。"
    return "\n".join([
        *lines,
        "执行方式：这些是软约束。优先保持自然表达，偏好词只在语境合适时使用，不要为了贴近画像而牺牲文章完整性。",
    ])


def _format_references(references: list) -> str:
    if not references:
        return "没有检索到可用参考片段。"

    strategy = _retrieval_strategy(references)
    intro = (
        "这些是从语义相关候选片段中经风格重排选出的风格示例片段，主要用于借鉴表达方式，禁止直接复制。"
        if strategy == "smart_rerank"
        else "这些是语义相关片段；rerank 不可用时会降级为语义检索，主要作为内容和表达参考，禁止直接复制。"
    )
    blocks = [intro]
    for index, item in enumerate(references, start=1):
        chunk, similarity = item
        title = chunk.chunk_metadata.get("article_title", "未知文章") if chunk.chunk_metadata else "未知文章"
        style_score = getattr(item, "style_score", None)
        semantic_score = getattr(item, "semantic_score", None)
        reason = (getattr(item, "rerank_reason", None) or "").strip()
        score_parts = [f"语义相似度 {similarity:.3f}"]
        if isinstance(style_score, (int, float)):
            score_parts.append(f"风格分 {style_score:.2f}")
        if isinstance(semantic_score, (int, float)):
            score_parts.append(f"语义分 {semantic_score:.2f}")
        reason_line = f"\n入选原因：{reason}" if reason else ""
        blocks.append(
            f"【风格示例片段 {index}｜{'｜'.join(score_parts)}｜{title}｜chunk#{chunk.chunk_index + 1}】"
            f"{reason_line}\n{chunk.content.strip()}"
        )
    return "\n\n".join(blocks)


def _format_length(payload: GenerationCreate) -> str:
    if payload.length_preset == "自定义":
        return f"约 {payload.custom_word_count} 字"
    mapping = {
        "短": "短，约 600-900 字",
        "中": "中，约 1200-1800 字",
        "长": "长，约 2200-3500 字",
    }
    return mapping[payload.length_preset]


def _imitation_instruction(strength: str) -> str:
    mapping = {
        "轻微模仿": "只借鉴节奏、语气和结构，不强行复刻用词。",
        "中度模仿": "明显参考句式、段落推进、修辞和情绪色彩。",
        "高度模仿": "更强地贴近画像中的句式、节奏、意象和收束方式，但仍不得复制旧文片段。",
    }
    return mapping[strength]


def _build_metadata(
    payload: GenerationCreate,
    profile: StyleProfile,
    references: list,
    system_prompt: str,
    user_prompt: str,
    operation_type: str,
) -> dict:
    operation_label = OPERATION_LABELS[operation_type]
    return {
        "user_input": payload.user_input,
        "writing_type": payload.writing_type,
        "custom_writing_type": payload.custom_writing_type,
        "length_preset": payload.length_preset,
        "custom_word_count": payload.custom_word_count,
        "imitation_strength": payload.imitation_strength,
        "include_references": payload.include_references,
        "extra_requirements": payload.extra_requirements,
        "referenced_chunk_ids": [str(chunk.id) for chunk, _similarity in references],
        **_retrieval_metadata(payload.include_references, references),
        "retrieved_chunks": _references_metadata(references),
        "style_profile_snapshot": _style_profile_snapshot(profile),
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
        "operation_type": operation_type,
        "operation_label": operation_label,
        "source_generation_id": None,
        "source_output_id": None,
        "display_title": _build_display_title({"user_input": payload.user_input}, operation_label if operation_type != "initial" else None),
        "debug_prompt_modified": False,
        "model": settings.llm_model,
        "reasoning_effort": GENERATION_REASONING_EFFORT,
        "thinking": {"type": "enabled"},
    }


def _build_revision_metadata(
    payload: GenerationRevise,
    profile: StyleProfile,
    references: list,
    system_prompt: str,
    user_prompt: str,
    source_task: GenerationTask,
    source_output: GeneratedOutput,
    source_metadata: dict,
) -> dict:
    operation_label = OPERATION_LABELS[payload.operation_type]
    return {
        **source_metadata,
        "operation_type": payload.operation_type,
        "operation_label": operation_label,
        "custom_instruction": payload.custom_instruction,
        "include_references": payload.include_references,
        "source_generation_id": str(source_task.id),
        "source_output_id": str(source_output.id),
        "display_title": _build_display_title(source_metadata, operation_label),
        "debug_prompt_modified": False,
        "referenced_chunk_ids": [str(chunk.id) for chunk, _similarity in references],
        **_retrieval_metadata(payload.include_references, references),
        "retrieved_chunks": _references_metadata(references),
        "style_profile_snapshot": _style_profile_snapshot(profile),
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
        "model": settings.llm_model,
        "reasoning_effort": GENERATION_REASONING_EFFORT,
        "thinking": {"type": "enabled"},
    }


def _retrieval_metadata(include_references: bool, references: list) -> dict:
    if not include_references:
        return {
            "retrieval_strategy": DISABLED_RETRIEVAL_STRATEGY,
            "candidate_chunk_count": 0,
            "rerank_model": None,
            "reranked_chunks": [],
        }
    return {
        "retrieval_strategy": _retrieval_strategy(references),
        "candidate_chunk_count": _candidate_count(references),
        "rerank_model": _rerank_model(references),
        "reranked_chunks": _reranked_metadata(references),
    }


def _retrieval_strategy(references: list) -> str:
    if not references:
        return "semantic_fallback"
    return str(getattr(references[0], "retrieval_strategy", "semantic_fallback"))


def _candidate_count(references: list) -> int:
    if not references:
        return 0
    value = getattr(references[0], "candidate_count", 0)
    return value if isinstance(value, int) else 0


def _rerank_model(references: list) -> str | None:
    if not references:
        return None
    value = getattr(references[0], "rerank_model", None)
    return value if isinstance(value, str) else None


def _reranked_metadata(references: list) -> list[dict]:
    return [
        {
            "id": str(item.chunk.id),
            "source_article_id": str(item.chunk.source_article_id),
            "chunk_index": item.chunk.chunk_index,
            "similarity": float(item.similarity),
            "style_score": getattr(item, "style_score", None),
            "semantic_score": getattr(item, "semantic_score", None),
            "reason": getattr(item, "rerank_reason", None),
            "retrieval_strategy": getattr(item, "retrieval_strategy", "semantic_fallback"),
        }
        for item in references
    ]


def _references_metadata(references: list) -> list[dict]:
    return [
        {
            "id": str(chunk.id),
            "source_article_id": str(chunk.source_article_id),
            "chunk_index": chunk.chunk_index,
            "similarity": float(similarity),
            "style_score": getattr(item, "style_score", None),
            "semantic_score": getattr(item, "semantic_score", None),
            "rerank_reason": getattr(item, "rerank_reason", None),
            "retrieval_strategy": getattr(item, "retrieval_strategy", "semantic_fallback"),
            "content": chunk.content,
            "metadata": chunk.chunk_metadata or {},
        }
        for item in references
        for chunk, similarity in [item]
    ]


def _style_profile_snapshot(profile: StyleProfile) -> dict:
    return {field_name: getattr(profile, field_name) for field_name in PROFILE_FIELD_NAMES}


def _build_display_title(metadata: dict, suffix: str | None = None) -> str:
    base = str(metadata.get("display_title") or metadata.get("user_input") or "生成记录").strip()
    if " - " in base:
        base = base.split(" - ", 1)[0].strip()
    base = base[:32] if len(base) > 32 else base
    return f"{base} - {suffix}" if suffix else base


def _payload_from_source_metadata(source_task: GenerationTask, metadata: dict) -> GenerationCreate:
    return GenerationCreate(
        style_category_id=source_task.style_category_id,
        writing_type=str(metadata.get("writing_type") or "散文"),
        custom_writing_type=metadata.get("custom_writing_type") if isinstance(metadata.get("custom_writing_type"), str) else None,
        user_input=str(metadata.get("user_input") or "请重新生成一版。"),
        length_preset=str(metadata.get("length_preset") or "中"),
        custom_word_count=metadata.get("custom_word_count") if isinstance(metadata.get("custom_word_count"), int) else None,
        imitation_strength=str(metadata.get("imitation_strength") or "中度模仿"),
        include_references=bool(metadata.get("include_references", True)),
        extra_requirements=metadata.get("extra_requirements") if isinstance(metadata.get("extra_requirements"), str) else None,
    )


def _call_deepseek(system_prompt: str, user_prompt: str) -> str:
    client = OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)
    response = client.chat.completions.create(
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        reasoning_effort=GENERATION_REASONING_EFFORT,
        extra_body={"thinking": {"type": "enabled"}},
        stream=False,
    )
    content = response.choices[0].message.content or ""
    if not content.strip():
        raise RuntimeError("DeepSeek 没有返回正文")
    return content.strip()


def _call_deepseek_stream(system_prompt: str, user_prompt: str) -> Iterator[tuple[str, str]]:
    client = OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)
    response = client.chat.completions.create(
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        reasoning_effort=GENERATION_REASONING_EFFORT,
        extra_body={"thinking": {"type": "enabled"}},
        stream=True,
    )
    for chunk in response:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        reasoning_content = getattr(delta, "reasoning_content", None) or ""
        if reasoning_content:
            yield ("progress", "")
        content = getattr(delta, "content", None) or ""
        if content:
            yield ("delta", content)


def _sse_event(event: str, data: dict) -> str:
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"


def _stream_error_message(exc: Exception) -> str:
    if isinstance(exc, HTTPException):
        return str(exc.detail)
    return str(exc) or "请求失败"


def _to_generation_read(task: GenerationTask) -> GenerationRead:
    outputs = sorted(task.outputs, key=lambda output: output.created_at, reverse=True)
    return GenerationRead(
        id=task.id,
        style_category_id=task.style_category_id,
        prompt=task.prompt,
        status=task.status,
        created_at=task.created_at,
        updated_at=task.updated_at,
        output=outputs[0] if outputs else None,
    )
