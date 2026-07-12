-- sqlite-vec vec0 virtual tables — created lazily, NOT by init_db().
--
-- See app/database.py's `ensure_vector_schema()`: this file is read and
-- templated (the __EMBEDDING_DIM__ placeholder substituted with a real
-- vector's length) the first time `vector_store.upsert_vector()` is ever
-- called on a given DB file, not at app startup - vec0 tables fix their
-- column width at CREATE TABLE time, and at startup nothing has produced
-- a real embedding yet to size them from.
--
-- One table per embedding *source* (PRD Section 3 "Embedding Model
-- Selection" / Section 4 "Vector Collection"). `rowid` is reused straight
-- from the corresponding pages/documents row (NOT a fresh identity) so a
-- vec0 match result's rowid joins directly back:
-- `SELECT * FROM pages WHERE rowid = ?`. distance_metric=cosine so
-- "distance" here is cosine distance (1 - cosine_similarity) — see
-- app/services/retrieval_service.py.
CREATE VIRTUAL TABLE IF NOT EXISTS page_content_vec  USING vec0(embedding FLOAT[__EMBEDDING_DIM__] distance_metric=cosine);
CREATE VIRTUAL TABLE IF NOT EXISTS page_summary_vec  USING vec0(embedding FLOAT[__EMBEDDING_DIM__] distance_metric=cosine);
CREATE VIRTUAL TABLE IF NOT EXISTS page_keywords_vec USING vec0(embedding FLOAT[__EMBEDDING_DIM__] distance_metric=cosine);
CREATE VIRTUAL TABLE IF NOT EXISTS document_vec      USING vec0(embedding FLOAT[__EMBEDDING_DIM__] distance_metric=cosine);
