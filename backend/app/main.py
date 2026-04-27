"""
Paper RAG backend — one FastAPI app, two route areas, per PRD Section 6:

    "The two halves are named Research (2.B) and Ingestion (2.A). They're
    separate route areas in a single Vue app... One FastAPI backend serves
    both, split into /api/research/* and /api/ingestion/* routers."

Run with: `uvicorn app.main:app --reload` (see README.md).
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.routers import ingestion, research


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Paper RAG", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(research.router)
app.include_router(ingestion.router)


@app.get("/api/health")
def health() -> dict[str, str | bool]:
    return {"status": "ok", "mock_mode": settings.MOCK_MODE}
