from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
import logging
import math
import re
from statistics import median

try:
    import jieba
except ImportError:  # pragma: no cover - dependency is declared, fallback keeps API usable.
    jieba = None

if jieba is not None:
    jieba.setLogLevel(logging.WARNING)

from app.models.article import SourceArticle
from app.services.articles import count_words

SENTENCE_SPLIT_RE = re.compile(r"[^。！？!?；;\n]+[。！？!?；;]?", re.MULTILINE)
PARAGRAPH_SPLIT_RE = re.compile(r"\n{2,}")
CHINESE_WORD_RE = re.compile(r"[\u4e00-\u9fff]{2,}")
PRIVATE_PHRASE_RE = re.compile(r"[\u4e00-\u9fff]{2,6}")

PUNCTUATION_MARKS = {
    "comma": ["，", ","],
    "period": ["。", "."],
    "question": ["？", "?"],
    "exclamation": ["！", "!"],
    "colon": ["：", ":"],
    "semicolon": ["；", ";"],
    "dash": ["——", "—", "-"],
    "ellipsis": ["……", "..."],
    "quote": ["“", "”", "‘", "’", "\"", "'"],
}

STOPWORDS = {
    "一个", "一种", "一些", "这个", "那个", "这些", "那些", "自己", "我们", "你们", "他们", "它们", "没有",
    "不是", "因为", "所以", "如果", "那么", "然后", "只是", "就是", "还是", "或者", "但是", "可是", "已经",
    "可以", "可能", "觉得", "知道", "时候", "什么", "这样", "那样", "这里", "那里", "其实", "或者", "还有",
    "以及", "对于", "关于", "通过", "进行", "成为", "不会", "不能", "不要", "需要", "所有", "很多", "非常",
}

CONNECTOR_WORDS = [
    "但是", "可是", "然而", "不过", "因此", "所以", "于是", "然后", "同时", "而且", "并且", "甚至",
    "尤其", "事实上", "换句话说", "反过来", "某种意义上", "问题是", "更重要的是",
]
PARTICLE_WORDS = ["吧", "呢", "啊", "嘛", "罢了", "而已", "似的", "一样", "大概", "或许"]
ABSTRACT_WORDS = [
    "意义", "存在", "命运", "时间", "生活", "现实", "关系", "秩序", "自由", "孤独", "真相", "记忆",
    "经验", "判断", "价值", "困境", "世界", "自我", "情绪", "本质",
]


def analyze_style_metrics(articles: list[SourceArticle]) -> dict:
    texts = [article.cleaned_text or "" for article in articles if (article.cleaned_text or "").strip()]
    joined_text = "\n\n".join(texts)
    paragraphs = _extract_paragraphs(texts)
    sentences = _extract_sentences(texts)
    sentence_lengths = [count_words(sentence) for sentence in sentences if count_words(sentence) > 0]
    paragraph_lengths = [count_words(paragraph) for paragraph in paragraphs if count_words(paragraph) > 0]

    return {
        "article_count": len(texts),
        "total_word_count": sum(count_words(text) for text in texts),
        "syntax": _syntax_metrics(sentence_lengths),
        "punctuation": _punctuation_metrics(joined_text),
        "paragraphs": _paragraph_metrics(paragraph_lengths, texts),
        "vocabulary": _vocabulary_metrics(joined_text),
        "structure": _structure_metrics(texts),
        "generated_at": datetime.now(UTC).isoformat(),
    }


def summarize_metrics_for_prompt(metrics: dict) -> str:
    syntax = metrics.get("syntax") or {}
    punctuation = metrics.get("punctuation") or {}
    paragraphs = metrics.get("paragraphs") or {}
    vocabulary = metrics.get("vocabulary") or {}
    structure = metrics.get("structure") or {}

    top_words = _join_words(vocabulary.get("top_words"))
    private_phrases = _join_words(vocabulary.get("private_phrases"))
    dominant_marks = ", ".join(punctuation.get("dominant_marks") or []) or "无明显偏好"
    tags = ", ".join(structure.get("tags") or []) or "未识别出稳定结构"

    return "\n".join([
        f"句法：平均句长 {syntax.get('avg_sentence_length', 0)}，中位句长 {syntax.get('median_sentence_length', 0)}，"
        f"短句比例 {syntax.get('short_sentence_ratio', 0)}，长句比例 {syntax.get('long_sentence_ratio', 0)}。",
        f"标点：主要标点偏好为 {dominant_marks}。",
        f"段落：平均段落长度 {paragraphs.get('avg_paragraph_length', 0)}，短段比例 {paragraphs.get('short_paragraph_ratio', 0)}，"
        f"长段比例 {paragraphs.get('long_paragraph_ratio', 0)}。",
        f"词汇：高频偏好词 {top_words or '无'}；个人化短语 {private_phrases or '无'}。",
        f"结构：{tags}。",
    ])


def _extract_sentences(texts: list[str]) -> list[str]:
    sentences: list[str] = []
    for text in texts:
        sentences.extend(match.group(0).strip() for match in SENTENCE_SPLIT_RE.finditer(text) if match.group(0).strip())
    return sentences


def _extract_paragraphs(texts: list[str]) -> list[str]:
    paragraphs: list[str] = []
    for text in texts:
        paragraphs.extend(paragraph.strip() for paragraph in PARAGRAPH_SPLIT_RE.split(text) if paragraph.strip())
    return paragraphs


def _syntax_metrics(lengths: list[int]) -> dict:
    if not lengths:
        return {
            "sentence_count": 0,
            "avg_sentence_length": 0,
            "median_sentence_length": 0,
            "short_sentence_ratio": 0,
            "medium_sentence_ratio": 0,
            "long_sentence_ratio": 0,
            "sample_sentence_lengths": [],
        }
    short_count = sum(1 for length in lengths if length <= 15)
    long_count = sum(1 for length in lengths if length >= 45)
    medium_count = len(lengths) - short_count - long_count
    return {
        "sentence_count": len(lengths),
        "avg_sentence_length": _round(sum(lengths) / len(lengths)),
        "median_sentence_length": _round(float(median(lengths))),
        "short_sentence_ratio": _ratio(short_count, len(lengths)),
        "medium_sentence_ratio": _ratio(medium_count, len(lengths)),
        "long_sentence_ratio": _ratio(long_count, len(lengths)),
        "sample_sentence_lengths": lengths[:80],
    }


def _punctuation_metrics(text: str) -> dict:
    total_chars = max(count_words(text), 1)
    counts = {
        name: sum(text.count(mark) for mark in marks)
        for name, marks in PUNCTUATION_MARKS.items()
    }
    per_1000_chars = {name: _round(count / total_chars * 1000) for name, count in counts.items()}
    dominant_marks = [
        _punctuation_label(name)
        for name, _count in sorted(counts.items(), key=lambda item: item[1], reverse=True)
        if _count > 0
    ][:4]
    return {
        "total_punctuation": sum(counts.values()),
        "counts": counts,
        "per_1000_chars": per_1000_chars,
        "dominant_marks": dominant_marks,
    }


def _paragraph_metrics(lengths: list[int], texts: list[str]) -> dict:
    opening_lengths: list[int] = []
    ending_lengths: list[int] = []
    for text in texts:
        paragraphs = _extract_paragraphs([text])
        if paragraphs:
            opening_lengths.append(count_words(paragraphs[0]))
            ending_lengths.append(count_words(paragraphs[-1]))

    if not lengths:
        return {
            "paragraph_count": 0,
            "avg_paragraph_length": 0,
            "median_paragraph_length": 0,
            "short_paragraph_ratio": 0,
            "long_paragraph_ratio": 0,
            "opening_avg_length": 0,
            "ending_avg_length": 0,
        }

    short_count = sum(1 for length in lengths if length <= 80)
    long_count = sum(1 for length in lengths if length >= 260)
    return {
        "paragraph_count": len(lengths),
        "avg_paragraph_length": _round(sum(lengths) / len(lengths)),
        "median_paragraph_length": _round(float(median(lengths))),
        "short_paragraph_ratio": _ratio(short_count, len(lengths)),
        "long_paragraph_ratio": _ratio(long_count, len(lengths)),
        "opening_avg_length": _round(sum(opening_lengths) / len(opening_lengths)) if opening_lengths else 0,
        "ending_avg_length": _round(sum(ending_lengths) / len(ending_lengths)) if ending_lengths else 0,
    }


def _vocabulary_metrics(text: str) -> dict:
    words = _tokenize(text)
    word_counts = Counter(word for word in words if _is_style_word(word))
    phrase_counts = Counter(_iter_private_phrases(text))
    return {
        "top_words": _top_items(word_counts, 30),
        "connectors": _matched_terms(text, CONNECTOR_WORDS),
        "particles": _matched_terms(text, PARTICLE_WORDS),
        "abstract_words": _matched_terms(text, ABSTRACT_WORDS),
        "private_phrases": _top_items(phrase_counts, 20),
    }


def _structure_metrics(texts: list[str]) -> dict:
    scores = Counter()
    opening_patterns = Counter()
    for text in texts:
        paragraphs = _extract_paragraphs([text])
        first = paragraphs[0] if paragraphs else text[:160]
        full = text[:1200]
        if re.search(r"[？?]", first):
            scores["question_opening"] += 1
            opening_patterns["问句切入"] += 1
        if re.search(r"(我|他|她|我们).{0,20}(看见|听见|走|坐|站|来到|回到|醒来|发现)", first):
            scores["scene_opening"] += 1
            opening_patterns["场景切入"] += 1
        if re.search(r"(其实|本质|意义|问题是|真正|不是|是)", first):
            scores["conclusion_first"] += 1
            opening_patterns["判断先行"] += 1
        if re.search(r"(但是|可是|然而|不过|反过来|问题是)", full):
            scores["contrast_turn"] += 1
        if re.search(r"(首先|其次|然后|接着|最后|于是|再后来|进一步)", full):
            scores["progressive"] += 1
        if re.search(r"(因为|所以|因此|这意味着|换句话说|也就是说)", full):
            scores["argumentative"] += 1

    tags = [_structure_label(key) for key, count in scores.most_common() if count > 0]
    return {
        "tags": tags[:5],
        "scores": dict(scores),
        "opening_patterns": _top_items(opening_patterns, 6),
    }


def _tokenize(text: str) -> list[str]:
    if jieba is not None:
        return [word.strip() for word in jieba.lcut(text) if word.strip()]
    return CHINESE_WORD_RE.findall(text)


def _is_style_word(word: str) -> bool:
    if len(word) < 2 or word in STOPWORDS:
        return False
    if word.isdigit():
        return False
    return bool(CHINESE_WORD_RE.fullmatch(word))


def _iter_private_phrases(text: str):
    cleaned = re.sub(r"\s+", "", text)
    for match in PRIVATE_PHRASE_RE.finditer(cleaned):
        phrase = match.group(0)
        if phrase not in STOPWORDS and len(set(phrase)) > 1:
            yield phrase


def _matched_terms(text: str, terms: list[str]) -> list[dict]:
    counts = Counter({term: text.count(term) for term in terms if text.count(term) > 0})
    return _top_items(counts, 20)


def _top_items(counter: Counter, limit: int) -> list[dict]:
    return [{"text": text, "count": count} for text, count in counter.most_common(limit) if count > 0]


def _join_words(items: object) -> str:
    if not isinstance(items, list):
        return ""
    return "、".join(str(item.get("text")) for item in items if isinstance(item, dict) and item.get("text"))


def _ratio(part: int, total: int) -> float:
    return _round(part / total) if total else 0


def _round(value: float) -> float:
    if math.isnan(value) or math.isinf(value):
        return 0
    return round(value, 3)


def _punctuation_label(name: str) -> str:
    labels = {
        "comma": "逗号",
        "period": "句号",
        "question": "问号",
        "exclamation": "感叹号",
        "colon": "冒号",
        "semicolon": "分号",
        "dash": "破折号",
        "ellipsis": "省略号",
        "quote": "引号",
    }
    return labels.get(name, name)


def _structure_label(key: str) -> str:
    labels = {
        "question_opening": "问句切入",
        "scene_opening": "场景切入",
        "conclusion_first": "判断先行",
        "contrast_turn": "转折推进",
        "progressive": "递进叙述",
        "argumentative": "论证推进",
    }
    return labels.get(key, key)
