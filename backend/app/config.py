"""
Central configuration for Paper RAG's backend.

Everything here is overridable via environment variables (or a `.env` file —
see `.env.example` at the repo root). Defaults are chosen so the app runs
out of the box in MOCK_MODE, without a GPU or Ollama installed, per the
notes in README.md and AGENT_TASKS.md.
"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/config.py -> backend/
BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Runtime mode -------------------------------------------------
    # MOCK_MODE=True routes every AI call (OCR/VLM, embeddings, generation)
    # through the deterministic mock providers in app/providers so the
    # whole app (API, pipeline, DB, retrieval, scenario classification)
    # is runnable and testable without a GPU or Ollama installed.
    # Flip to False once Ollama is running with the real models pulled
    # (see README.md "Going from mock to real models").
    MOCK_MODE: bool = True

    # --- Storage --------------------------------------------------------
    DB_PATH: Path = BACKEND_DIR / "storage" / "paper_rag.sqlite3"
    HUEY_DB_PATH: Path = BACKEND_DIR / "storage" / "huey.sqlite3"
    PDF_STORAGE_DIR: Path = BACKEND_DIR / "storage" / "pdfs"
    PROMPTS_DIR: Path = BACKEND_DIR / "prompts"

    # --- Ollama-served models (section 5 of the PRD) --------------------
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_TIMEOUT_SECONDS: float = 120.0

    # Model tags as pulled into Ollama. These are placeholders — see
    # AGENT_TASKS.md for pulling/serving the real olmOCR / Mistral / BGE-M3
    # weights under Ollama.
    OCR_MODEL: str = "olmocr"
    GENERATION_MODEL: str = "mistral-small"
    EMBEDDING_MODEL: str = "bge-m3"
    EMBEDDING_DIM: int = 1024

    # --- Ingestion pipeline tuning ---------------------------------------
    METADATA_SOURCE_PAGE_COUNT: int = 3  # first N pages combined for metadata (2.A #2)
    SHORT_PAGE_SENTENCE_THRESHOLD: int = 5  # below this, skip summary/keywords (Section 3)

    # --- Retrieval (2.B #1, #2, #6 + Section 3 "Precision Re-ranking") ---
    RETRIEVAL_TOP_K: int = 8
    # Weights across the three page-level embedding sources when combining
    # scores. Kept in config rather than a DB table for v1 — see AGENT_TASKS
    # if this needs to become admin-editable at runtime.
    EMBEDDING_WEIGHT_CONTENT: float = 0.50
    EMBEDDING_WEIGHT_SUMMARY: float = 0.35
    EMBEDDING_WEIGHT_KEYWORDS: float = 0.15

    # Scenario classification thresholds on the combined cosine similarity
    # of the top hit (2.B #2). "Dynamic thresholding" per PRD Section 3 is
    # approximated here with configurable static cutoffs — see AGENT_TASKS
    # for turning this into a corpus-calibrated / gap-based scheme.
    SCENARIO_HIGH_THRESHOLD: float = 0.75  # >= this -> database_only
    SCENARIO_MID_THRESHOLD: float = 0.55  # >= this -> hybrid
    SCENARIO_LOW_THRESHOLD: float = 0.35  # >= this -> model_first; below -> model_only

    # --- CORS (dev) -------------------------------------------------------
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]


settings = Settings()

# Make sure storage directories exist at import time — keeps first-run friction low.
settings.PDF_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
settings.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
settings.HUEY_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
