"""Depolama — the single persistence gateway (doc 29).

Every durable read/write in the Çekirdek goes through this package: no other
subsystem opens a raw SQLite handle or writes SQL (doc 29 §9/§21, PR-2/PR-13).
Concrete implementations of the subsystem repository Protocols (doc 11/12/13)
live here in ``repos/``; this package depends on those contracts, never the
reverse (DIP — the composition root injects the implementations).
"""

from turkish_code.depo.alan import StorageEngine, WorkspaceStore
from turkish_code.depo.baglanti import Connection, Row, SqliteConnection
from turkish_code.depo.blobs import BlobHash, BlobStore
from turkish_code.depo.db import Database
from turkish_code.depo.islem import Transaction
from turkish_code.depo.journal import Journal, JournalRecord
from turkish_code.depo.migrate import Migration, load_migrations, migrate
from turkish_code.depo.yerlesim import StorageLayout

__all__ = [
    "StorageLayout",
    "StorageEngine",
    "WorkspaceStore",
    "Database",
    "Connection",
    "SqliteConnection",
    "Transaction",
    "Row",
    "Migration",
    "load_migrations",
    "migrate",
    "BlobStore",
    "BlobHash",
    "Journal",
    "JournalRecord",
]
