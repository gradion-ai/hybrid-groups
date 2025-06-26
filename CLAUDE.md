# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Setup

- @.cursor/rules/project-setup.mdc

### Common Commands

- @.cursor/rules/running-tests.mdc
- @.cursor/rules/project-dependencies.mdc

Additional commands are:

#### Code checks

Before running code-checks ensure that the relevant files are staged using `git add`

```bash
# Code quality checks (linting, formatting, type checking)
invoke code-check
invoke cc  # alias
```

#### Commands for web development

Always run the following commands for changes you apply to the web UI (the `web` folder):
* code linting: `npm run lint`
* check for typescript compiling issues: `npx tsc --noEmit`
