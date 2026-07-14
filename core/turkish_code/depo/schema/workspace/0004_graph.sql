-- Knowledge graph nodes and edges (doc 12 §4). Workspace DB only (doc 29 §5).
-- Traversal (neighbors/path/subgraph/impact, doc 12 §8) walks graph_edge via
-- recursive CTEs; the source/target indexes keep those bounded walks fast.
CREATE TABLE graph_node (
    id            TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    kind          TEXT NOT NULL,
    file_path     TEXT,
    start_line    INTEGER,
    end_line      INTEGER,
    language      TEXT,
    signature     TEXT,
    summary       TEXT,
    embedding_ref TEXT,
    embedder_id   TEXT,
    embedding_dim INTEGER,
    salience      REAL NOT NULL,
    run_id        TEXT,
    event_id      TEXT,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
) STRICT;

CREATE TABLE graph_edge (
    source     TEXT NOT NULL,
    target     TEXT NOT NULL,
    kind       TEXT NOT NULL,
    run_id     TEXT,
    event_id   TEXT,
    created_at TEXT NOT NULL,
    PRIMARY KEY (source, target, kind)
) STRICT;

CREATE INDEX idx_graph_edge_source ON graph_edge (source);
CREATE INDEX idx_graph_edge_target ON graph_edge (target);
CREATE INDEX idx_graph_node_name ON graph_node (name);
