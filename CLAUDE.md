# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Setup

- @.cursor/rules/project-setup.mdc

### Common Commands

- @.cursor/rules/running-tests.mdc
- @.cursor/rules/project-dependencies.mdc

Additional commands are:

```bash
# Code quality checks (linting, formatting, type checking)
# IMPORTANT: code quality checks only work for files that have been added to git
invoke code-check
invoke cc  # alias

# Documentation
invoke build-docs  # Build documentation with MkDocs
invoke serve-docs  # Serve documentation locally at http://localhost:8000
invoke deploy-docs  # Deploy documentation to GitHub Pages
```
