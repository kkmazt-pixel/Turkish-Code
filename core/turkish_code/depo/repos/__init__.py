"""Concrete SQLite repositories (doc 29 §9/§11).

Each module here implements a subsystem's repository Protocol (doc 11/12/13)
over the :mod:`turkish_code.depo` connection layer. They depend on those
contracts, never the reverse (DIP) — the composition root injects them.
"""
