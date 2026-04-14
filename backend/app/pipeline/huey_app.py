"""
Huey task queue instance — PRD Section 5.

SQLite-backed (no Redis/broker), and meant to run with exactly one worker
(concurrency=1): with a single shared GPU, concurrent tasks would fight
over VRAM (model-swap thrashing between the OCR VLM, BGE-M3, and the
generation LLM), so ingestion is a strict FIFO over documents rather than
a parallel pool. The "-w 1" is enforced at the consumer invocation (see
README.md), not something this module can force by itself — don't run
`huey_consumer.py` with `-w` greater than 1 for this app.
"""

from __future__ import annotations

from huey import SqliteHuey

from app.config import settings

huey = SqliteHuey(filename=str(settings.HUEY_DB_PATH))
