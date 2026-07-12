-- Paper RAG core schema (relational tables only).
--
-- The four sqlite-vec vec0 virtual tables live in schema_vectors.sql and
-- are created lazily, not here - see app/database.py's
-- `ensure_vector_schema()` and its module-level comment for why.

PRAGMA foreign_keys = ON;

-- =====================================================================
-- Documents  (PRD Section 4 "Document")
-- =====================================================================
CREATE TABLE IF NOT EXISTS documents (
    id                      TEXT PRIMARY KEY,          -- sha256(file bytes)
    file_name               TEXT NOT NULL,
    file_path               TEXT NOT NULL,              -- storage/pdfs/<id>.pdf
    total_pages             INTEGER NOT NULL DEFAULT 0,

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

    metadata_status         TEXT NOT NULL DEFAULT 'pending',
    metadata_edited_by_admin INTEGER NOT NULL DEFAULT 0,

    running_summary         TEXT,

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

    content_text        TEXT,
    content_text_fixed  INTEGER NOT NULL DEFAULT 0,

    extractor_used      TEXT,

    is_short_page       INTEGER NOT NULL DEFAULT 0,

    page_summary        TEXT,
    keywords_json        TEXT,

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

    retrieved_pages_json     TEXT,

    created_at              TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_queries_created_at ON queries(created_at);
