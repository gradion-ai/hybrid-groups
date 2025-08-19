# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Dependency Management

To add a dependency to the project, run the following command:

```bash
uv add <dependency>
```

To remove a dependency from the project, run the following command:

```bash
uv remove <dependency>
```

Add optional arguments like `--dev` for development dependencies, for example, as needed.

For syncing dependencies after a manual change of `pyproject.toml`, run the following command:

```bash
uv sync
```

### Running Tests

#### General
- `uv run invoke test` for running all unit and integration tests.
- `uv run invoke test --cov` for running all unit and integration tests and generating a coverage report.

#### Unit Tests
- `uv run invoke ut` for running unit tests.
- `uv run invoke ut --cov` for running unit tests and generating a coverage report.

#### Integration Tests
- `uv run invoke it` for running all integration tests.
- `uv run invoke it --cov` for running all integration tests and generating a coverage report.
- `uv run pytest -xsv tests/integration/test_[name].py` for running a single integration test file.
- `uv run pytest -xsv tests/integration/test_[name].py::[test-name]` for running a single integration test.

All invoke test commands use `-xsv` flags by default for verbose output and stopping on first failure.
Coverage reports are displayed in the terminal and cover the `ipybox` package.

### Code Quality

To run code quality checks (linting, formatting, type checking), run the following command:

```bash
uv run invoke code-check
uv run invoke cc  # alias
```

IMPORTANT: The `code-check` command automatically fixes most issues:
- Auto-fixed: Formatting issues (black, isort, etc.) are corrected automatically
- Manual fix required: Type checking errors (mypy) must be fixed manually by you
- No need to manually reformat code - the command handles it for you

### Documentation

To build the documentation, run the following command:

```bash
uv run invoke build-docs
```

To serve the documentation locally at `http://localhost:8000`, run the following command:

```bash
uv run invoke serve-docs
```

## Common Workflows

IMPORTANT: After making ANY code changes (including simple edits), you MUST:

1. If you created any NEW files (untracked files), add them to git with `git add <new-file>`. This is needed for code quality checks to work. Note: You do NOT need to add files that are already tracked by git (i.e., files you only edited).
2. Run code quality checks with `uv run invoke cc`.
3. Run all unit and integration tests with `uv run invoke test`.

This workflow applies to:
- Adding new features
- Fixing bugs
- Refactoring code
- Making ANY edits to Python files, no matter how small
- Updating configuration values
- Changing imports or dependencies

If you see any errors, fix them and then repeat the process.

## Architecture Overview

The `hygroup` package implements a multi-user, multi-agent collaboration platform that enables users to interact with agents and other users in group chats on Slack and GitHub.

### Core Package Structure

- **`hygroup/`**: Main package containing all core functionality
  - **`session.py`**: Central session management orchestrating all components
  - **`agent/`**: Agent implementations and abstractions
  - **`gateway/`**: Platform integrations (Slack, GitHub, Terminal)
  - **`user/`**: User management, permissions, and preferences
  - **`setup/`**: Web-based setup application for configuring platform integrations
  - **`scripts/`**: Entry points for running servers and utilities

### Session Management

The `Session` class in `hygroup/session.py` is the central orchestrator that:
- Manages the lifecycle of multi-user, multi-agent conversations (group sessions)
- Maintains conversation history and state persistence
- Coordinates between gateways, agents, and users
- Handles message routing and agent activation

Key interactions:
- Each session corresponds to a Slack thread or GitHub issue
- Sessions instantiate and manage `SessionAgent` instances that wrap agents with session context
- Sessions communicate with gateways to send/receive messages from platforms
- Sessions persist state to disk for resumption after restarts

### Gateway Abstraction

The gateway layer (`hygroup/gateway/`) provides platform-agnostic interfaces:

- **`base.py`**: Defines the `Gateway` abstract base class
- **`slack/gateway.py`**: Slack implementation handling threads, reactions, and app home
- **`github/gateway.py`**: GitHub implementation for issues and comments
- **`terminal.py`**: Terminal interface for local testing

Gateways handle:
- Platform-specific message formatting and threading
- User authentication and identity mapping
- Emoji reactions for agent activation feedback
- Bidirectional communication between sessions and platforms

### Agent Architecture

The agent system (`hygroup/agent/`) provides flexible agent implementations:

- **`base.py`**: Core abstractions (`Agent`, `Message`, `AgentRequest`, `AgentResponse`)
- **`system/`**: System agent that orchestrates subagents via tools
  - `agent.py`: SystemAgent implementation using Pydantic AI
  - `prompt.py`: System agent instructions for analyzing messages and routing to subagents
- **`default/`**: Default agent implementations
  - `agent.py`: Base Pydantic AI agent implementation
  - `registry.py`: Agent registry for managing available agents

The **SystemAgent** is special:
- Analyzes incoming messages to determine if assistance is needed
- Can invoke registered subagents as tools based on their capabilities
- Manages user preferences and permission checks
- Routes requests to appropriate specialized agents

### User Management

The user system (`hygroup/user/`) handles identity and permissions:

- **`base.py`**: Core user abstractions (`User`, `UserRegistry`, `PermissionStore`)
- **`default/`**: Default implementations
  - `registry.py`: User registry with identity mapping across platforms
  - `permission.py`: Permission store for tool approval workflows
  - `preferences.py`: User preference management
  - `channel.py`: User communication channels for permission requests

Key features:
- Users can set preferences that agents respect
- Tool executions require user approval (once, session, or always)
- Secrets are encrypted and isolated per user

### Platform-Specific Features

**Slack Integration** (`hygroup/gateway/slack/`):
- App home interface for agent builder and user settings
- Ephemeral messages for permission requests
- Thread-based session management
- Socket mode for real-time communication

**GitHub Integration** (`hygroup/gateway/github/`):
- Webhook-based event handling
- Issue and comment management
- GitHub App authentication
- Emoji reactions for agent feedback
