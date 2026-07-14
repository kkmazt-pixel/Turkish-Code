-- FTS5 lexical index over RAG chunk text (doc 13 §6, doc 29 §7). Workspace DB
-- only: chunks are per-project. BM25 keyword search complements the vector
-- index in hybrid retrieval — essential for exact identifiers/paths vectors
-- miss (doc 13 §6). remove_diacritics 0 keeps Turkish characters (ş/ı/İ/ğ/ç/ö/ü)
-- intact so casing/diacritics are not mangled; the RAG layer splits
-- camelCase/snake_case before text reaches this substrate. chunk_id is stored
-- UNINDEXED so upserts replace by id (delete-then-insert) and results carry the
-- id back. FTS5 virtual tables cannot be STRICT.
CREATE VIRTUAL TABLE chunk_fts USING fts5(
    chunk_id UNINDEXED,
    body,
    tokenize = "unicode61 remove_diacritics 0"
);
