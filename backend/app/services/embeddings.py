import tiktoken
from openai import OpenAI

from app.core.config import settings

_encoding = tiktoken.get_encoding("cl100k_base")


def get_embeddings(texts: list[str]) -> list[list[float]]:
    if not settings.embedding_api_key:
        raise RuntimeError("EMBEDDING_API_KEY is not configured")

    client = OpenAI(
        api_key=settings.embedding_api_key,
        base_url=settings.embedding_base_url,
    )

    batch_size = 6
    all_embeddings: list[list[float]] = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        response = client.embeddings.create(
            model=settings.embedding_model,
            input=batch,
            dimensions=1536,
        )
        all_embeddings.extend(item.embedding for item in response.data)
    return all_embeddings


def count_tokens(text: str) -> int:
    return len(_encoding.encode(text))
