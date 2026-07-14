"""Content-addressed blob store (doc 29 §6) — BLAKE3, sharded, refcounted.

Blobs are keyed by their **BLAKE3** content hash (ADR-B, fixed project-wide,
doc 29 §24) and stored sharded by hash prefix (``blobs/ab/cd/<hash>``). Writes
are idempotent: identical content yields the same key and is stored once (dedup,
doc 29 §6). A durable write goes temp-file → fsync → atomic rename so a crash
never leaves a half-written blob (doc 29 §8/§14).

Content lives on the filesystem; the **refcount** lives in the workspace DB
(``blob_refcount``). A blob's bytes are reclaimed by :meth:`collect_garbage`
only when nothing references it — which also sweeps orphaned files that were
written but never retained (doc 29 §14).
"""

from __future__ import annotations

import asyncio
import os
import uuid
from dataclasses import dataclass
from pathlib import Path

import blake3

from turkish_code.depo.db import Database

_HEX_DIGITS: frozenset[str] = frozenset("0123456789abcdef")
_HASH_LEN = 64  # BLAKE3 default 32-byte digest, hex-encoded


def _is_blob_hash(value: str) -> bool:
    return len(value) == _HASH_LEN and set(value) <= _HEX_DIGITS


@dataclass(frozen=True, slots=True)
class BlobHash:
    """A BLAKE3 content hash (hex). Distinct from the SHA-256 entity-id space."""

    value: str

    def __post_init__(self) -> None:
        if not _is_blob_hash(self.value):
            raise ValueError(f"not a BLAKE3 hex digest: {self.value!r}")


class BlobStore:
    """A content-addressed blob store over one workspace's ``blobs/`` dir."""

    def __init__(self, blobs_dir: Path, db: Database, *, fsync: bool) -> None:
        self._root = blobs_dir
        self._db = db
        self._fsync = fsync

    async def put(self, data: bytes) -> BlobHash:
        """Store ``data`` (idempotent) and return its hash (doc 29 §6)."""
        return await asyncio.to_thread(self._put_sync, data)

    async def get(self, blob_hash: BlobHash) -> bytes | None:
        """Return the blob's bytes, or ``None`` if it isn't stored."""
        return await asyncio.to_thread(self._get_sync, blob_hash)

    async def exists(self, blob_hash: BlobHash) -> bool:
        """Whether the blob's content is on disk."""
        return await asyncio.to_thread(self._path(blob_hash).exists)

    async def retain(self, blob_hash: BlobHash) -> None:
        """Add one reference to ``blob_hash`` (doc 29 §6)."""
        async with self._db.transaction() as tx:
            await tx.execute(
                "INSERT INTO blob_refcount (hash, count) VALUES (?, 1) "
                "ON CONFLICT(hash) DO UPDATE SET count = count + 1",
                (blob_hash.value,),
            )

    async def release(self, blob_hash: BlobHash) -> None:
        """Drop one reference; the row is removed at zero (GC-eligible)."""
        async with self._db.transaction() as tx:
            await tx.execute(
                "UPDATE blob_refcount SET count = count - 1 WHERE hash = ?",
                (blob_hash.value,),
            )
            await tx.execute("DELETE FROM blob_refcount WHERE count <= 0")

    async def collect_garbage(self) -> int:
        """Delete every on-disk blob with no positive refcount; return the count.

        Reconciles orphans too: a blob written by :meth:`put` but never retained
        has no refcount row and is swept here (doc 29 §14).
        """
        rows = await self._db.fetchall("SELECT hash FROM blob_refcount WHERE count > 0")
        referenced = {row["hash"] for row in rows}
        return await asyncio.to_thread(self._sweep, referenced)

    def _put_sync(self, data: bytes) -> BlobHash:
        blob_hash = BlobHash(blake3.blake3(data).hexdigest())
        path = self._path(blob_hash)
        if path.exists():
            return blob_hash  # dedup: identical content stored once
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.parent / f".{path.name}.{uuid.uuid4().hex}.tmp"
        with open(tmp, "wb") as handle:
            handle.write(data)
            if self._fsync:
                handle.flush()
                os.fsync(handle.fileno())
        os.replace(tmp, path)
        if self._fsync:
            self._fsync_dir(path.parent)
        return blob_hash

    def _get_sync(self, blob_hash: BlobHash) -> bytes | None:
        path = self._path(blob_hash)
        try:
            return path.read_bytes()
        except FileNotFoundError:
            return None

    def _sweep(self, referenced: set[str]) -> int:
        reclaimed = 0
        if not self._root.exists():
            return 0
        for path in self._root.glob("*/*/*"):
            name = path.name
            if not path.is_file() or not _is_blob_hash(name):
                continue  # skip in-flight temp files; collect only real blobs
            if name not in referenced:
                path.unlink()
                reclaimed += 1
        return reclaimed

    def _path(self, blob_hash: BlobHash) -> Path:
        value = blob_hash.value
        return self._root / value[:2] / value[2:4] / value

    @staticmethod
    def _fsync_dir(directory: Path) -> None:
        fd = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
