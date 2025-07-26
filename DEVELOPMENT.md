# Development Environment

This guide provides instructions for setting up a development environment for `hybrid-groups`. Follow these steps to get started with development, testing, and contributing to the project.

Clone the repository:

```bash
git clone https://github.com/gradion-ai/hybrid-groups.git
cd hybrid-groups
```

Install dependencies and create virtual environment:

```bash
uv sync
```

Activate the virtual environment:

```bash
source .venv/bin/activate
```

Install pre-commit hooks:

```bash
invoke precommit-install
```

Enforce coding conventions (also enforced by pre-commit hooks):

```bash
invoke cc
```

Run tests:

```bash
pytest -s tests
```
