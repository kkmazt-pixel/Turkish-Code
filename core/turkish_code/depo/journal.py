"""Append-only event journal (doc 29 §7, ADR-F) — the durable ordered log.

Records are length-prefixed and CRC32-checksummed: ``[len:4][crc32:4][payload]``
(big-endian). Appends are fsync'd (durability-critical, doc 29 §8) and serialized
(single-writer). A record's ordinal position is its ``seq`` (1-based, monotonic).

On open the log is scanned and a **corrupt tail** — a torn or bad-CRC trailing
record from an interrupted append — is truncated to the last valid record (no
silent data loss, doc 29 §7/§14). The SQLite Timeline projection is *derived*
from this log and rebuildable (doc 26/29), so the journal is the source of truth.

The log is a single active segment today; segment rotation (doc 29 §7) is a
future extension behind this same append/read API (doc 29 §19).
"""

from __future__ import annotations

import asyncio
import os
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Final

_HEADER = struct.Struct(">II")  # (payload_length, crc32)
_HEADER_SIZE: Final = _HEADER.size
MAX_RECORD_BYTES: Final = 64 * 1024 * 1024
SEGMENT_NAME: Final = "000001.log"


@dataclass(frozen=True, slots=True)
class JournalRecord:
    """One durable log record and its 1-based sequence number (doc 29 §7)."""

    seq: int
    payload: bytes


class Journal:
    """A single-writer, fsync'd, append-only event log (doc 29 §7)."""

    def __init__(self, path: Path, *, fsync: bool, head: int) -> None:
        self._path = path
        self._fsync = fsync
        self._head = head
        self._append_lock = asyncio.Lock()

    @classmethod
    async def open(cls, journal_dir: Path, *, fsync: bool) -> Journal:
        """Open the log, truncating any corrupt tail from an interrupted append."""
        path = journal_dir / SEGMENT_NAME
        head = await asyncio.to_thread(cls._recover, path)
        return cls(path, fsync=fsync, head=head)

    def head(self) -> int:
        """The sequence number of the last durable record (0 if empty)."""
        return self._head

    async def append(self, payload: bytes) -> int:
        """Append ``payload`` durably and return its sequence number (doc 29 §7)."""
        if len(payload) > MAX_RECORD_BYTES:
            raise ValueError(f"record exceeds {MAX_RECORD_BYTES} bytes")
        async with self._append_lock:
            seq = await asyncio.to_thread(self._append_sync, payload)
            self._head = seq
            return seq

    async def read_from(self, seq: int) -> list[JournalRecord]:
        """Every record with sequence number >= ``seq`` (tail-replay, doc 28 §16)."""
        records = await asyncio.to_thread(self._read_all)
        return [r for r in records if r.seq >= seq]

    def _append_sync(self, payload: bytes) -> int:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        frame = _HEADER.pack(len(payload), zlib.crc32(payload)) + payload
        with open(self._path, "ab") as handle:
            handle.write(frame)
            if self._fsync:
                handle.flush()
                os.fsync(handle.fileno())
        return self._head + 1

    def _read_all(self) -> list[JournalRecord]:
        return self._scan_path(self._path, truncate=False)

    @classmethod
    def _recover(cls, path: Path) -> int:
        return len(cls._scan_path(path, truncate=True))

    @staticmethod
    def _scan_path(path: Path, *, truncate: bool) -> list[JournalRecord]:
        if not path.exists():
            return []
        records: list[JournalRecord] = []
        with open(path, "rb") as handle:
            data = handle.read()
        offset = 0
        valid_end = 0
        while offset + _HEADER_SIZE <= len(data):
            length, crc = _HEADER.unpack(data[offset : offset + _HEADER_SIZE])
            body_start = offset + _HEADER_SIZE
            body_end = body_start + length
            if length > MAX_RECORD_BYTES or body_end > len(data):
                break  # torn trailing record
            payload = data[body_start:body_end]
            if zlib.crc32(payload) != crc:
                break  # corrupt trailing record
            records.append(JournalRecord(seq=len(records) + 1, payload=payload))
            offset = body_end
            valid_end = body_end
        if truncate and valid_end != len(data):
            os.truncate(path, valid_end)
        return records
