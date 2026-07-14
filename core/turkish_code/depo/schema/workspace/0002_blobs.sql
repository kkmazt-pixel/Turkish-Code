-- Blob refcount table (doc 29 §6). Content lives on the filesystem CAS
-- (blobs/ab/cd/<blake3>); this tracks how many durable referrers (snapshot
-- records, timeline blobRefs) hold each blob. GC reclaims a blob's bytes only
-- once nothing references it (count reaches 0 and the row is removed).
CREATE TABLE blob_refcount (
    hash  TEXT PRIMARY KEY,
    count INTEGER NOT NULL DEFAULT 0
) STRICT;
