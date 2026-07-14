"""Versioned DDL + migration scripts — the schema source of truth (doc 29 §9/§11).

Each DB kind (``app``, ``workspace``) has its own numbered, forward-only
``NNNN_name.sql`` migrations under a subdirectory here. The runner
(:mod:`turkish_code.depo.migrate`) applies pending ones atomically at startup.
"""
