-- Memory items (doc 11 §5). The App DB holds global-scoped and profile memory
-- (doc 29 §5); the schema is identical to the Workspace DB's memory table
-- (which holds workspace-scoped rows) — same shape, different scope of rows.
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
