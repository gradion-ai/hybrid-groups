# Development Guide

This guide provides instructions for setting up a development environment for `hybrid-groups`. Follow these steps to get started with development, testing, and contributing to the project.

Clone the repository:

```bash
git clone https://github.com/gradion-ai/hybrid-groups.git
cd hybrid-groups
```

Create a new Conda environment and activate it:

```bash
conda env create -f environment.yml
conda activate hybrid-groups
```

Install the poetry dynamic versioning plugin:

```bash
poetry self add "poetry-dynamic-versioning[plugin]"
```

Install dependencies with Poetry:

```bash
poetry install
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
