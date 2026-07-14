-- Memory items (doc 11 §5). Workspace-scoped memory lives in the Workspace DB
-- (doc 29 §5). `forgotten` is a storage-internal soft-delete tombstone (doc 11
-- §10): forgotten rows are retained for audit but excluded from recall; purge
-- hard-deletes the row. `links` is a JSON array of graph entity ids (doc 12).
CREATE TABLE memory (
    id            TEXT PRIMARY KEY,
    layer         TEXT NOT NULL,
    scope         TEXT NOT NULL,
    kind          TEXT NOT NULL,
    state         TEXT NOT NULL,
    title         TEXT NOT NULL,
    body          TEXT NOT NULL,
    links         TEXT NOT NULL,
    embedding_ref TEXT,
    embedder_id   TEXT,
    embedding_dim INTEGER,
    salience      REAL NOT NULL,
    run_id        TEXT,
    event_id      TEXT,
    pinned        INTEGER NOT NULL,
    created_at    TEXT NOT NULL,
    last_used_at  TEXT NOT NULL,
    use_count     INTEGER NOT NULL,
    confidence    REAL NOT NULL,
    ttl_seconds   REAL,
    forgotten     INTEGER NOT NULL DEFAULT 0
) STRICT;

CREATE INDEX idx_memory_recall ON memory (scope, layer, forgotten, state);
