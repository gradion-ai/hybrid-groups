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
```

## Available MCP Tools for Development

When developing with this codebase, you have access to the following MCP tools:

### Context7 MCP Server
Use the `context7` MCP server to fetch the latest documentation for any library. This is particularly useful when:
- Working with external dependencies
- Needing up-to-date API references
- Understanding library usage patterns
