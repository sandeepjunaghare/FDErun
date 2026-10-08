"""Voyage embeddings: input_type "document" at ingest, "query" at search."""

from typing import Literal

import voyageai.error
from voyageai.client_async import AsyncClient

from config import get_settings

BATCH = 128  # texts per Voyage request


class EmbeddingError(Exception):
    """Embedding failed: missing key, API error, or a vector of the wrong size."""


async def embed(texts: list[str], input_type: Literal["document", "query"]) -> list[list[float]]:
    """Embed texts with EMBEDDING_MODEL at EMBEDDING_DIM. Raises EmbeddingError."""
    settings = get_settings()
    if not settings.voyage_api_key:
        raise EmbeddingError("VOYAGE_API_KEY not set")
    client = AsyncClient(api_key=settings.voyage_api_key)
    vectors: list[list[float]] = []
    for start in range(0, len(texts), BATCH):
        try:
            result = await client.embed(
                texts[start : start + BATCH],
                model=settings.embedding_model,
                input_type=input_type,
                output_dimension=settings.embedding_dim,
            )
        except voyageai.error.VoyageError as exc:
            raise EmbeddingError(type(exc).__name__) from exc
        vectors.extend([float(x) for x in v] for v in result.embeddings)
    if any(len(v) != settings.embedding_dim for v in vectors):
        raise EmbeddingError(f"expected {settings.embedding_dim}-dim vectors (vector(N) column)")
    return vectors


def to_pgvector(vector: list[float]) -> str:
    """Format a vector as a pgvector literal, used with %s::vector."""
    return "[" + ",".join(map(str, vector)) + "]"
