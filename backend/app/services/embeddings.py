"""Provider-agnostic embeddings.

``HashEmbedder`` produces deterministic, dependency-free vectors — the default under tests
and for pipeline development, so the full ingestion + hybrid-search path is exercisable
offline. ``FastEmbedEmbedder`` produces real multilingual (Arabic/English) embeddings via
fastembed's ONNX runtime (no torch), selected with ``EMBEDDING_PROVIDER=local``.
"""

import asyncio
import hashlib
import math
import os
import struct
from functools import lru_cache
from typing import Protocol

from app.config import get_settings

settings = get_settings()


class EmbeddingClient(Protocol):
    provider: str
    dim: int

    async def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    async def embed_query(self, text: str) -> list[float]: ...


class HashEmbedder:
    provider = "hash"

    def __init__(self, dim: int = 1024) -> None:
        self.dim = dim

    def _vector(self, text: str) -> list[float]:
        values: list[float] = []
        counter = 0
        while len(values) < self.dim:
            block = hashlib.sha256(f"{counter}:{text}".encode()).digest()
            for offset in range(0, len(block), 4):
                if len(values) >= self.dim:
                    break
                (raw,) = struct.unpack("<I", block[offset : offset + 4])
                values.append((raw / 2**32) * 2 - 1)
            counter += 1
        norm = math.sqrt(sum(v * v for v in values)) or 1.0
        return [v / norm for v in values]

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    async def embed_query(self, text: str) -> list[float]:
        return self._vector(text)


class FastEmbedEmbedder:
    """Real embeddings. The e5 family expects ``passage:``/``query:`` prefixes. The model is
    downloaded once and cached; embedding is CPU-bound so it runs in a worker thread."""

    provider = "local"

    def __init__(self, *, model_name: str, dim: int, cache_dir: str | None = None) -> None:
        from fastembed import TextEmbedding

        self.dim = dim
        self._model = TextEmbedding(model_name=model_name, cache_dir=cache_dir)

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        prefixed = [f"passage: {text}" for text in texts]
        return await asyncio.to_thread(
            lambda: [vector.tolist() for vector in self._model.embed(prefixed)]
        )

    async def embed_query(self, text: str) -> list[float]:
        vectors = await asyncio.to_thread(
            lambda: list(self._model.embed([f"query: {text}"]))
        )
        return vectors[0].tolist()


@lru_cache
def get_embedder() -> EmbeddingClient:
    provider = "hash" if os.environ.get("TESTING") else settings.embedding_provider
    if provider == "hash":
        return HashEmbedder(dim=settings.embedding_dimensions)
    return FastEmbedEmbedder(
        model_name=settings.embedding_model,
        dim=settings.embedding_dimensions,
        cache_dir=settings.fastembed_cache_dir,
    )
