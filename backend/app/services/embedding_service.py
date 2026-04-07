"""
Embedding providers — PRD Section 5 (`BGE-M3`, served through Ollama).

`MockEmbeddingProvider` is a real, deterministic implementation of the
*interface* (same shape, same dimension), just not of the *semantics* — it
produces a reproducible pseudo-random unit vector per input string rather
than a meaningful multilingual embedding. That's enough to exercise every
piece of plumbing around it (sqlite-vec inserts, cosine search, weighted
re-ranking, scenario-threshold math) without a GPU. It is not a substitute
for validating retrieval quality — see AGENT_TASKS.md.
"""

from __future__ import annotations

import hashlib
import math
import random
from typing import Protocol

from app.config import settings
from app.providers.ollama_client import OllamaClient


class EmbeddingProvider(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


class OllamaEmbeddingProvider:
    """Real implementation, calling BGE-M3 as served by Ollama. Not
    exercised against a live server in this environment — see
    AGENT_TASKS.md."""

    def __init__(self, client: OllamaClient | None = None):
        self._client = client or OllamaClient()

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return self._client.embed(model=settings.EMBEDDING_MODEL, texts=texts)


class MockEmbeddingProvider:
    """Deterministic, dependency-free stand-in. Same input string always
    produces the same unit vector; different strings produce
    (uncorrelated, non-semantic) different vectors."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(t) for t in texts]

    @staticmethod
    def _embed_one(text: str) -> list[float]:
        seed = int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16) % (2**32)
        rng = random.Random(seed)
        vec = [rng.gauss(0.0, 1.0) for _ in range(settings.EMBEDDING_DIM)]
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]


def get_embedding_provider() -> EmbeddingProvider:
    if settings.MOCK_MODE:
        return MockEmbeddingProvider()
    return OllamaEmbeddingProvider()
