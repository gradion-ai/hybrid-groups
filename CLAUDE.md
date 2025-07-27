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
invoke code-check
invoke cc  # alias

# Documentation
invoke build-docs  # Build documentation with MkDocs
invoke serve-docs  # Serve documentation locally at http://localhost:8000
invoke deploy-docs  # Deploy documentation to GitHub Pages
```

### Common Workflows

IMPORTANT: After making ANY code changes (including simple edits), you MUST:

1. If you created any NEW files (untracked files), add them to git with `git add <new-file>`. This is needed for code quality checks to work. Note: You do NOT need to add files that are already tracked by git (i.e., files you only edited).
2. Run code quality checks with `invoke cc`.
3. Run all unit and integration tests with `pytest -s tests/`.

This workflow applies to:
- Adding new features
- Fixing bugs
- Refactoring code
- Making ANY edits to Python files, no matter how small
- Updating configuration values
- Changing imports or dependencies

If you see any errors, fix them and then repeat the process.
