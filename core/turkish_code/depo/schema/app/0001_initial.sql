-- App DB baseline (doc 29 §5). Global, non-workspace state lives here.
-- The meta table is durable key/value provenance — e.g. the schema baseline
-- marker and, later, the embedder id/dim a store was built with (doc 14 §9).
CREATE TABLE meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
) STRICT;
