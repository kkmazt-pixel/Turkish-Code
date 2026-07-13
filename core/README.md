# Çekirdek (`core/`)

The **Çekirdek** is turkish.code's Python 3.12+ AI-brain sidecar. It hosts all
AI/business logic and speaks the Core Channel (JSON-RPC over stdio) to the
Kabuk. It performs no user-world side effects directly — those are brokered by
the Kabuk (doc [09](../docs/09_PYTHON_BACKEND.md) §9).

- **Architecture:** [docs/09_PYTHON_BACKEND.md](../docs/09_PYTHON_BACKEND.md)
- **Layout & tooling:** [docs/37_REPOSITORY_STRUCTURE.md](../docs/37_REPOSITORY_STRUCTURE.md)
- **Coding standards:** [docs/36_CODING_STANDARDS.md](../docs/36_CODING_STANDARDS.md)

## Development

```bash
# From a Python 3.12+ environment, install with dev tooling:
pip install -e ".[dev]"

pytest          # tests
ruff check .    # lint (bans print(), enforces imports/style)
black .         # format
mypy            # strict type-check
```

## Modules

Each subdirectory of `turkish_code/` is one subsystem, named with the canonical
Turkish term (ASCII-transliterated, doc 44 §2). Implemented so far (foundation):

- `hata/` — typed error taxonomy and `AppError` value (doc 38).
- `ortak/` — shared kernel: `Clock` and `LogLevel` (doc 09 §10).
- `yapilandirma/` — layered configuration + path resolution (doc 33).
- `gunluk/` — structured stderr logger + redaction (doc 39).
- `kanal/` — Core Channel message contract + server interface (doc 10).
- `kompozisyon.py` — the composition root / dependency-injection wiring (doc 09 §7).
