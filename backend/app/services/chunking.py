from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class ChunkResult:
    content: str
    chunk_index: int
    position: str
    paragraph_count: int


def _count_chars(text: str) -> int:
    return len(text)


def _split_long_paragraph(text: str, max_chars: int) -> list[str]:
    sentences: list[str] = []
    for part in re.split(r"(?<=[。！？；\n.!?;])", text):
        if part.strip():
            sentences.append(part)
    if not sentences:
        segments = []
        while text:
            segments.append(text[:max_chars])
            text = text[max_chars:]
        return segments

    segments: list[str] = []
    current = ""
    for sentence in sentences:
        if current and _count_chars(current + sentence) > max_chars:
            segments.append(current)
            current = ""
            
        while _count_chars(sentence) > max_chars:
            segments.append(sentence[:max_chars])
            sentence = sentence[max_chars:]
            
        if sentence:
            current += sentence
            
    if current:
        segments.append(current)
    return segments


def chunk_article(
    cleaned_text: str,
    article_title: str,
    min_chars: int = 300,
    max_chars: int = 800,
    overlap_chars: int = 100,
) -> list[ChunkResult]:
    paragraphs = [p.strip() for p in cleaned_text.split("\n\n") if p.strip()]
    if not paragraphs:
        return []

    raw_chunks: list[tuple[str, int]] = []
    current_parts: list[str] = []
    current_count = 0
    para_count = 0

    for para in paragraphs:
        para_chars = _count_chars(para)

        if para_chars > max_chars:
            sub_segments = _split_long_paragraph(para, max_chars)
            
            if current_parts:
                if current_count < min_chars // 2 and sub_segments:
                    sub_segments[0] = "\n\n".join(current_parts) + "\n\n" + sub_segments[0]
                else:
                    raw_chunks.append(("\n\n".join(current_parts), para_count))
                current_parts = []
                current_count = 0
                para_count = 0

            for seg in sub_segments[:-1]:
                raw_chunks.append((seg, 1))
            
            if sub_segments:
                current_parts = [sub_segments[-1]]
                current_count = _count_chars(sub_segments[-1])
                para_count = 1
            continue

        if current_count + para_chars > max_chars and current_count >= min_chars:
            raw_chunks.append(("\n\n".join(current_parts), para_count))
            current_parts = []
            current_count = 0
            para_count = 0

        current_parts.append(para)
        current_count += para_chars
        para_count += 1

    if current_parts:
        if raw_chunks and current_count < min_chars // 2:
            prev_text, prev_para_count = raw_chunks[-1]
            merged = prev_text + "\n\n" + "\n\n".join(current_parts)
            raw_chunks[-1] = (merged, prev_para_count + para_count)
        else:
            raw_chunks.append(("\n\n".join(current_parts), para_count))

    if not raw_chunks:
        return []

    total = len(raw_chunks)
    results: list[ChunkResult] = []

    for i, (text, p_count) in enumerate(raw_chunks):
        if i > 0 and overlap_chars > 0:
            prev_text = raw_chunks[i - 1][0]
            overlap = prev_text[-overlap_chars:]
            text = overlap + "\n\n" + text

        if i == 0:
            position = "beginning"
        elif i == total - 1:
            position = "end"
        else:
            position = "middle"

        results.append(ChunkResult(
            content=text,
            chunk_index=i,
            position=position,
            paragraph_count=p_count,
        ))

    return results
