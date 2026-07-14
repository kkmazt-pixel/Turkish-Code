"""Tests for the append-only event journal (doc 29 §7/§14, ADR-F).

Real files on disk, real fsync, real byte-level corruption — a mock could not
prove tail-truncation or checksum detection.
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

import pytest
from turkish_code.depo.journal import Journal


async def _open(tmp_path: Path) -> Journal:
    return await Journal.open(tmp_path, fsync=True)


@pytest.mark.asyncio
async def test_fresh_journal_is_empty(tmp_path: Path) -> None:
    journal = await _open(tmp_path)
    assert journal.head() == 0
    assert await journal.read_from(1) == []


@pytest.mark.asyncio
async def test_append_assigns_monotonic_seq(tmp_path: Path) -> None:
    journal = await _open(tmp_path)
    assert await journal.append(b"a") == 1
    assert await journal.append(b"b") == 2
    assert await journal.append(b"c") == 3
    assert journal.head() == 3


@pytest.mark.asyncio
async def test_read_from_returns_tail(tmp_path: Path) -> None:
    journal = await _open(tmp_path)
    for payload in (b"one", b"two", b"three"):
        await journal.append(payload)
    tail = await journal.read_from(2)
    assert [(r.seq, r.payload) for r in tail] == [(2, b"two"), (3, b"three")]


@pytest.mark.asyncio
async def test_records_survive_reopen(tmp_path: Path) -> None:
    journal = await _open(tmp_path)
    await journal.append(b"durable")
    reopened = await _open(tmp_path)
    assert reopened.head() == 1
    assert (await reopened.read_from(1))[0].payload == b"durable"


@pytest.mark.asyncio
async def test_appends_after_reopen_continue_seq(tmp_path: Path) -> None:
    journal = await _open(tmp_path)
    await journal.append(b"first")
    reopened = await _open(tmp_path)
    assert await reopened.append(b"second") == 2


@pytest.mark.asyncio
async def test_binary_and_turkish_payloads_round_trip(tmp_path: Path) -> None:
    journal = await _open(tmp_path)
    payload = "İstanbul şğüçöı".encode() + b"\x00\xff\x01"
    await journal.append(payload)
    assert (await journal.read_from(1))[0].payload == payload


@pytest.mark.asyncio
async def test_torn_trailing_record_is_truncated_on_open(tmp_path: Path) -> None:
    journal = await _open(tmp_path)
    await journal.append(b"good1")
    await journal.append(b"good2")
    # Simulate an interrupted append: a header promising more bytes than exist.
    segment = tmp_path / "000001.log"
    with open(segment, "ab") as handle:
        handle.write(struct.pack(">II", 999, 0) + b"partial")

    reopened = await _open(tmp_path)
    assert reopened.head() == 2  # torn record dropped
    assert [r.payload for r in await reopened.read_from(1)] == [b"good1", b"good2"]
    # Truncation is durable: a subsequent append lands cleanly at seq 3.
    assert await reopened.append(b"good3") == 3


@pytest.mark.asyncio
async def test_bad_checksum_record_is_detected_and_truncated(tmp_path: Path) -> None:
    journal = await _open(tmp_path)
    await journal.append(b"valid")
    segment = tmp_path / "000001.log"
    body = b"tampered"
    wrong_crc = zlib.crc32(b"different")
    with open(segment, "ab") as handle:
        handle.write(struct.pack(">II", len(body), wrong_crc) + body)

    reopened = await _open(tmp_path)
    assert reopened.head() == 1
    assert [r.payload for r in await reopened.read_from(1)] == [b"valid"]


@pytest.mark.asyncio
async def test_read_does_not_mutate_the_log(tmp_path: Path) -> None:
    journal = await _open(tmp_path)
    await journal.append(b"x")
    segment = tmp_path / "000001.log"
    size_before = segment.stat().st_size
    await journal.read_from(1)
    assert segment.stat().st_size == size_before


@pytest.mark.asyncio
async def test_oversized_record_is_rejected(tmp_path: Path) -> None:
    from turkish_code.depo.journal import MAX_RECORD_BYTES

    journal = await _open(tmp_path)
    with pytest.raises(ValueError, match="exceeds"):
        await journal.append(b"x" * (MAX_RECORD_BYTES + 1))
