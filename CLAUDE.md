# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

```bash
uv sync                      # Install/sync dependencies
uv add <dep>                 # Add dependency (--dev for dev deps)
uv run invoke cc             # Run code checks (auto-fixes formatting, mypy errors need manual fix)
uv run invoke test           # Run all tests
uv run invoke ut             # Run unit tests only
uv run invoke it             # Run integration tests only
uv run invoke test --cov     # Run tests with coverage

# Single test file
uv run pytest -xsv tests/integration/test_[name].py

# Single test
uv run pytest -xsv tests/integration/test_[name].py::test_name

# Documentation
uv run invoke build-docs     # Build docs
uv run invoke serve-docs     # Serve docs at localhost:8000
```

**Note:** `invoke cc` only checks files under version control. Run `git add` on new files first.
