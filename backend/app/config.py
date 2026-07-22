"""
Central configuration for Paper RAG's backend.

Everything here is overridable via environment variables (or a `.env` file —
see `.env.example` at the repo root). Defaults are chosen so the app runs
out of the box in MOCK_MODE, without a GPU or any inference server, per the
notes in README.md and AGENT_TASKS.md.

Every self-hosted or hosted model role (OCR/vision, generation, embedding)
gets its own independent `ProviderSettings` instance below
(`ocr_settings` / `generation_settings` / `embedding_settings`), each
reading its own `<ROLE>_BASE_URL` / `<ROLE>_API_KEY` / `<ROLE>_MODEL` /
`<ROLE>_TIMEOUT_SECONDS` env vars via pydantic-settings' per-instance
`_env_prefix` override — nothing is shared or defaulted across roles,
since each commonly points at a different host, key, or provider (Ollama,
vLLM, OpenAI, Mistral, ...). See app/providers/model_client.py.

These are deliberately three separate `BaseSettings` instances rather than
one `Settings` field of nested `ProviderSettings` with
`env_nested_delimiter="_"` — the latter looks natural but doesn't work:
pydantic-settings' nested-delimiter matching splits an env var on *every*
underscore, so `OCR_BASE_URL` parses as three segments (`OCR`, `BASE`,
`URL`) instead of two (`OCR`, `BASE_URL`) and silently fails to populate
`base_url`. Giving each role its own `BaseSettings` subclass instance with
its own `_env_prefix` sidesteps that ambiguity entirely rather than working
around it (confirmed against pydantic-settings==2.14.2).
"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent


class ConfigError(RuntimeError):
    """Raised when a role's runtime configuration turns out to be
    insufficient to make a real (non-mocked) call - e.g. MOCK_MODE=False
    with no OCR_BASE_URL/OCR_MODEL set, an OpenAI-compatible call failing
    outright, or a configured EMBEDDING_DIM that the provider's actual
    response doesn't match (see embedding_service.py)."""


class ProviderSettings(BaseSettings):
    """One inference role's connection details.

    `base_url`/`model` default to `None` rather than being required so
    that construction succeeds with zero configuration in MOCK_MODE (the
    out-of-the-box default, and what the test suite always forces) - the
    `get_*_provider()` factories in each `*_service.py` are the ones that
    insist these are actually set, and only when building a real,
    non-mock provider.

    Every field here also independently supports `.env`/env var
    overrides (see `model_config`) - the concrete, role-scoped instances
    below (`ocr_settings` etc.) are what supply the `_env_prefix` that
    makes e.g. `OCR_BASE_URL` land on `ocr_settings.base_url`.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
    )

    base_url: str | None = None
    api_key: str = "not-needed"  # most self-hosted OpenAI-compatible
                                  # servers (Ollama, vLLM, TEI) ignore
                                  # auth, but the OpenAI SDK requires a
                                  # non-empty string
    model: str | None = None
    timeout_seconds: float = 120.0


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
    )

    MOCK_MODE: bool = True

    DB_PATH: Path = BACKEND_DIR / "storage" / "paper_rag.sqlite3"
    HUEY_DB_PATH: Path = BACKEND_DIR / "storage" / "huey.sqlite3"
    PDF_STORAGE_DIR: Path = BACKEND_DIR / "storage" / "pdfs"
    PROMPTS_DIR: Path = BACKEND_DIR / "prompts"

    # Optional. An assertion/truncation request for the embedding role,
    # not a schema requirement - see the "Embedding dimension handling"
    # docstring on EmbeddingProvider.embed() in embedding_service.py. Has
    # no bearing on vec0 table creation any more (see database.py -
    # ensure_vector_schema() sizes columns from a real vector's length,
    # not from this setting).
    EMBEDDING_DIM: int | None = None

    METADATA_SOURCE_PAGE_COUNT: int = 3
    SHORT_PAGE_SENTENCE_THRESHOLD: int = 5

    # ISSUE-011 (AGENT_TASKS.md): config-driven upload limits. Neither
    # existed before - anything, of any size or length, was accepted.
    # 100 MB comfortably covers a dense, image-heavy scientific PDF
    # without allowing an unbounded upload to fill disk or take an
    # unreasonable amount of time to hash/store/page-count. 1000 pages
    # covers even a large thesis/technical-report; a document longer than
    # that is more likely a bulk/mis-scanned file than a single paper,
    # and would take an impractical amount of single-GPU-worker time to
    # ingest one page at a time regardless.
    MAX_UPLOAD_FILE_SIZE_BYTES: int = 100 * 1024 * 1024
    MAX_UPLOAD_PAGE_COUNT: int = 1000

    # ISSUE-014 (AGENT_TASKS.md): bounds any single `_extract_page_text`/
    # `run_prompt` call in the ingestion pipeline (app/pipeline/tasks.py)
    # so a hung model call fails that step instead of blocking the
    # single-worker queue forever - see `_run_with_timeout`'s docstring
    # there. 5 minutes is well above AGENT_TASKS.md's own observed real
    # OCR latency (~1-2 min/page under GPU contention, per ISSUE-006's
    # notes) while still bounding a genuine hang to a human-noticeable,
    # bounded wait rather than an indefinite one.
    PAGE_PROCESSING_TIMEOUT_SECONDS: float = 300.0

    RETRIEVAL_TOP_K: int = 8
    EMBEDDING_WEIGHT_CONTENT: float = 0.50
    EMBEDDING_WEIGHT_SUMMARY: float = 0.35
    EMBEDDING_WEIGHT_KEYWORDS: float = 0.15

    # ISSUE-008 (AGENT_TASKS.md): the PRD's Section 3 says scenario
    # classification uses "dynamic thresholding" but doesn't define what
    # that means. These three absolute cutoffs on the combined top score
    # are kept as the tunable *base* tier boundaries - a fixed, static
    # thing by themselves, which is what "dynamic" can't just mean.
    SCENARIO_HIGH_THRESHOLD: float = 0.75
    SCENARIO_MID_THRESHOLD: float = 0.55
    SCENARIO_LOW_THRESHOLD: float = 0.35

    # The genuinely dynamic part: a per-query adjustment based on the
    # *shape* of the ranked list rather than the top score in isolation.
    # If the top hit doesn't clear the runner-up by at least this much,
    # the top score's absolute value doesn't necessarily mean the top
    # page is distinctly more relevant than everything else retrieved -
    # it may just mean every candidate scored similarly (e.g. a generic
    # query, or a corpus with a lot of near-duplicate content), which is
    # a weaker basis for "database_only" or "hybrid" confidence than the
    # same top score with a clear runner-up gap. `classify_scenario`
    # demotes one scenario tier (never promotes) when this margin is too
    # small. See app/services/retrieval_service.py::classify_scenario.
    SCENARIO_MARGIN_THRESHOLD: float = 0.05

    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]


settings = Settings()

# One independently-configured ProviderSettings per model role - see the
# module docstring for why these are separate instances (with their own
# `_env_prefix`) rather than nested fields on `Settings`.
ocr_settings = ProviderSettings(_env_prefix="OCR_")
generation_settings = ProviderSettings(_env_prefix="GENERATION_")
embedding_settings = ProviderSettings(_env_prefix="EMBEDDING_")

settings.PDF_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
settings.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
settings.HUEY_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
