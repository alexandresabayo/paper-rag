"""
Embedding provider — role-scoped, OpenAI-SDK based (see
app/providers/model_client.py and `embedding_settings` in app/config.py).

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

import openai

from app.config import ConfigError, embedding_settings, settings
from app.providers.model_client import get_client


class EmbeddingProviderProtocol(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


class EmbeddingProvider:
    """Real implementation, calling this role's configured
    OpenAI-compatible `/v1/embeddings` endpoint (BGE-M3, Cohere, OpenAI
    text-embedding-3-*, ...). Constructed with its own client + model,
    injected from `embedding_settings` — never shared with the generation
    or OCR roles' clients.

    Not exercised against a live server in this environment — see
    AGENT_TASKS.md.
    """

    def __init__(self, client: openai.OpenAI, model: str, dim: int | None = None):
        self._client = client
        self._model = model
        self._dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embedding dimension handling: `dim` is an assertion, not a
        command.

        - `dim` is None (EMBEDDING_DIM unset): never sent as a request
          parameter. The provider's native output width is used as-is;
          there is nothing to validate against. This is also what the
          vec0 tables end up sized to on a fresh DB — see
          `app.database.ensure_vector_schema`.
        - `dim` is set: sent optimistically as the OpenAI `dimensions=`
          truncation parameter (honored by e.g. OpenAI's
          text-embedding-3-*; ignored/rejected by most self-hosted
          fixed-dimension servers). On a 400, retry once without it. Once
          we have a response either way, every returned vector's length
          is validated against `dim` and a `ConfigError` is raised on
          mismatch rather than silently storing wrong-sized vectors.
        """
        if not texts:
            return []

        kwargs: dict = {"model": self._model, "input": texts}
        if self._dim is not None:
            kwargs["dimensions"] = self._dim

        try:
            response = self._client.embeddings.create(**kwargs)
        except openai.BadRequestError:
            if self._dim is None:
                raise
            # Provider doesn't support the `dimensions` truncation param
            # at all (fixed-dimension server, e.g. BGE-M3 behind
            # TEI/vLLM) - retry without it; the length check below still
            # runs against whatever it actually returns.
            kwargs.pop("dimensions")
            response = self._client.embeddings.create(**kwargs)
        except openai.OpenAIError as exc:
            raise ConfigError(f"Embedding call failed for model={self._model!r}: {exc}") from exc

        vectors = [d.embedding for d in sorted(response.data, key=lambda d: d.index)]

        if self._dim is not None:
            for vec in vectors:
                if len(vec) != self._dim:
                    raise ConfigError(
                        f"EMBEDDING_DIM={self._dim} but provider returned "
                        f"{len(vec)}-dim vectors. Either the model doesn't "
                        "support truncation, or the config is wrong — unset "
                        "EMBEDDING_DIM to auto-detect instead."
                    )
        return vectors


class MockEmbeddingProvider:
    """Deterministic, dependency-free stand-in. Same input string always
    produces the same unit vector; different strings produce
    (uncorrelated, non-semantic) different vectors.

    Uses `settings.EMBEDDING_DIM or 1024` rather than
    `settings.EMBEDDING_DIM` directly, since EMBEDDING_DIM is genuinely
    optional (`None` means "auto-detect from a real provider's response",
    which doesn't apply to a mock) — 1024 preserves this mock's original
    default width when nothing else has been configured.
    """

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(t) for t in texts]

    @staticmethod
    def _embed_one(text: str) -> list[float]:
        seed = int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16) % (2**32)
        rng = random.Random(seed)
        dim = settings.EMBEDDING_DIM or 1024
        vec = [rng.gauss(0.0, 1.0) for _ in range(dim)]
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]


def get_embedding_provider() -> EmbeddingProviderProtocol:
    if settings.MOCK_MODE:
        return MockEmbeddingProvider()
    if not embedding_settings.base_url or not embedding_settings.model:
        raise ConfigError(
            "MOCK_MODE is False but EMBEDDING_BASE_URL/EMBEDDING_MODEL are not set — see .env.example."
        )
    return EmbeddingProvider(
        client=get_client(embedding_settings),
        model=embedding_settings.model,
        dim=settings.EMBEDDING_DIM,
    )
