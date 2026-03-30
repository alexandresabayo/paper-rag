-- Paper RAG schema
--
-- Design notes (see docs/prd.md for the source spec):
--   * documents.id / pages.id are content-addressed (see app/utils/hashing.py),
--     not autoincrement — 2.A #11.
--   * Ordinary tables keep their implicit SQLite `rowid`; we reuse that as the
--     primary key column inside the sqlite-vec vec0 tables below rather than
--     inventing a second id, so a vec0 match result joins straight back with
--     `WHERE rowid = ?`.
--   * "N/A" fields (fallback path) are represented as SQL NULL, not the
--     string "N/A" — the API layer renders NULL as "N/A" for display. This
--     keeps "is this field missing" a simple `IS NULL` check everywhere.
--   * All AI-derived text fields (metadata, summaries, keywords) are
--     nullable for exactly this reason.

PRAGMA foreign_keys = ON;

-- =====================================================================
-- Documents  (PRD Section 4 "Document")
-- =====================================================================
CREATE TABLE IF NOT EXISTS documents (
    id                      TEXT PRIMARY KEY,          -- sha256(file bytes)
    file_name               TEXT NOT NULL,
    file_path               TEXT NOT NULL,              -- storage/pdfs/<id>.pdf
    total_pages             INTEGER NOT NULL DEFAULT 0,

    -- LLM-extracted metadata (2.A #2) — NULL until extracted, stays NULL
    -- ("N/A") forever if the VLM pipeline failed outright for this doc.
    doc_type                TEXT,                       -- Journal Article / Conference Paper / Preprint / Thesis / Technical Report
    authors_json            TEXT,                       -- JSON array of strings
    year                    TEXT,
    title                   TEXT,
    venue                   TEXT,
    doi                     TEXT,
    acronym                 TEXT,
    language                TEXT,                       -- detected primary language (2.A #3): 'en' | 'fr' | 'es' | ...
    license                 TEXT,
    source                  TEXT,                       -- owning repository

    -- 'pending' | 'done' | 'na' (na = VLM pipeline failed outright, see 2.A metadata fallback)
    metadata_status         TEXT NOT NULL DEFAULT 'pending',
    metadata_edited_by_admin INTEGER NOT NULL DEFAULT 0, -- Section 6(b) manual correction flag

    -- Cache of the folded incremental document summary (2.A #5). This is a
    -- *cache*, not a checkpoint: on resume it is cheaply rebuilt by
    -- re-folding over pages.page_summary in order, it is never trusted
    -- as-is mid-retry. Used as the source text for the document-level
    -- embedding.
    running_summary         TEXT,

    -- Document-level processing status, derived/maintained by the pipeline.
    -- 'pending' | 'processing' | 'done' | 'failed'
    status                  TEXT NOT NULL DEFAULT 'pending',
    last_error              TEXT,

    created_at              TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at              TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);

-- =====================================================================
-- Pages  (PRD Section 4 "Page")
-- =====================================================================
CREATE TABLE IF NOT EXISTS pages (
    id                  TEXT PRIMARY KEY,              -- "{document_id}:{page_number:05d}"
    document_id         TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    page_number         INTEGER NOT NULL,

    content_text        TEXT,                          -- transcribed (VLM) or raw (fallback) text
    content_text_fixed  INTEGER NOT NULL DEFAULT 0,     -- 1 if the encoding-repair table changed something (Section 3)

    -- 'vlm' (primary path) | 'fallback' (pypdf, worst case only)
    extractor_used      TEXT,

    is_short_page       INTEGER NOT NULL DEFAULT 0,     -- < SHORT_PAGE_SENTENCE_THRESHOLD sentences (Section 3)

    page_summary        TEXT,                           -- NULL when fallback / short page (N/A)
    keywords_json        TEXT,                          -- NULL when fallback / short page (N/A); else structured categories (Section 4 "Keyword Categories")

    -- 'pending' | 'done' | 'failed' — the checkpoint a retry resumes from (2.A #12)
    processing_status   TEXT NOT NULL DEFAULT 'pending',
    error_message        TEXT,

    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),

    UNIQUE (document_id, page_number)
);

CREATE INDEX IF NOT EXISTS idx_pages_document_id ON pages(document_id);
CREATE INDEX IF NOT EXISTS idx_pages_status ON pages(document_id, processing_status);

-- =====================================================================
-- Query history  (PRD Section 4 "User Query" / 2.B #5)
-- =====================================================================
CREATE TABLE IF NOT EXISTS queries (
    id                      TEXT PRIMARY KEY,          -- uuid4
    query_text              TEXT NOT NULL,
    response_text            TEXT,
    answer_mode              TEXT NOT NULL,             -- 'full_rag' | 'direct_model' (2.B #4)
    scenario                TEXT,                       -- 'database_only'|'hybrid'|'model_first'|'model_only', NULL for direct_model (2.B #2)

    -- JSON array of {document_id, document_title, page_number, similarity_score, snippet}
    -- rendered by the frontend as the lightweight inline/footer citation list.
    retrieved_pages_json     TEXT,

    created_at              TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_queries_created_at ON queries(created_at);

-- =====================================================================
-- Vector search (sqlite-vec) — PRD Section 4 "Vector Collection" +
-- Section 3 "Embedding Model Selection" (multiple weighted sources).
--
-- One vec0 table per embedding *source*. `rowid` is reused straight from
-- the corresponding pages/documents row (NOT a fresh identity) so a vec0
-- match result's rowid joins directly back: `SELECT * FROM pages WHERE
-- rowid = ?`. distance_metric=cosine so "distance" here is cosine
-- distance (1 - cosine_similarity) — see app/services/retrieval_service.py.
-- =====================================================================
CREATE VIRTUAL TABLE IF NOT EXISTS page_content_vec  USING vec0(embedding FLOAT[__EMBEDDING_DIM__] distance_metric=cosine);
CREATE VIRTUAL TABLE IF NOT EXISTS page_summary_vec  USING vec0(embedding FLOAT[__EMBEDDING_DIM__] distance_metric=cosine);
CREATE VIRTUAL TABLE IF NOT EXISTS page_keywords_vec USING vec0(embedding FLOAT[__EMBEDDING_DIM__] distance_metric=cosine);
CREATE VIRTUAL TABLE IF NOT EXISTS document_vec      USING vec0(embedding FLOAT[__EMBEDDING_DIM__] distance_metric=cosine);
