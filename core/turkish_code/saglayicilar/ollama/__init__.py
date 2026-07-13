"""Ollama — the local/offline fallback provider (doc 22 §5.5, doc 32)."""

from turkish_code.saglayicilar.ollama.adapter import create_ollama_provider

__all__ = ["create_ollama_provider"]
