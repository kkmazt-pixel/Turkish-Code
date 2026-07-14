-- Workspace DB baseline (doc 25 §4, doc 29 §5). Per-project derived state.
-- The meta table holds durable key/value provenance for this workspace —
-- e.g. its bound workspace id (doc 25 §4) and the embedder id/dim its vector
-- store was built with (doc 14 §9).
CREATE TABLE meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
) STRICT;
