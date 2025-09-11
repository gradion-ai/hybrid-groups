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
Coverage reports are displayed in the terminal and cover the `hygroup` package.

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

The `hygroup` package implements a multi-user AI collaboration system that enables AI agents to interact with human teams on platforms like Slack and GitHub. The architecture supports multiple users with individual permissions, preferences, and service integrations.

### Core Package Structure

- **`hygroup/`**: Main package containing all core functionality
  - **`session.py`**: Manages conversation sessions between users and agents, handling message routing, agent lifecycle, and state persistence
  - **`agent/`**: Agent framework with base abstractions, registry system, and implementations
  - **`gateway/`**: Platform integrations for Slack and GitHub, handling message delivery and user interactions
  - **`user/`**: User data management including settings, preferences, secrets, and custom commands
  - **`setup/`**: Web application for initial Slack/GitHub app configuration and OAuth setup
  - **`scripts/`**: Entry points for running the application server and managing Composio integrations
  - **`connect/`**: Composio connector enabling access to 250+ external services via MCP servers
  - **`channel.py`**: Request handlers for permission and feedback requests with different UI implementations

### `session` module

Orchestrates agent-user interactions within conversation sessions. Key responsibilities:
- Creates and manages `SessionAgent` instances that wrap agents with session context
- Handles message queuing and sequential processing
- Manages agent state persistence and restoration
- Coordinates between gateways, agents, and request handlers
- Supports command expansion for user-defined shortcuts

### `agent` package

Provides the agent framework and implementations:
- **`base.py`**: Core abstractions (`Agent`, `Message`, `AgentRequest`, `AgentResponse`, permissions)
- **`registry.py`**: `AgentRegistry` for managing agent configurations and `AgentRegistries` for channel-scoped registries
- **`default/`**: Default agent implementation using Pydantic AI with MCP server support
- **`system/`**: System agent that monitors all messages and can delegate to specialized agents
- **`utils.py`**: Helper functions for agent operations

### `gateway` package

Abstracts platform-specific communication:
- **`base.py`**: `Gateway` abstract base class defining the interface
- **`slack/`**: Slack integration using Socket Mode
  - Handles messages, threads, commands, and ephemeral interactions
  - Manages App Home for user preferences and secrets
  - Supports permission requests via ephemeral messages
- **`github/`**: GitHub App integration via webhooks
  - Processes issues, pull requests, and review comments
  - Maps GitHub events to agent requests
  - Uses smee.io for local development webhook delivery

### `user` package

Manages user-specific data:
- **`settings.py`**: `SettingsStore` for preferences, permissions, custom commands, and user mappings
- **`secrets.py`**: `SecretsStore` for encrypted storage of API keys and tokens using PBKDF2 encryption

### `setup` package

Web application for initial configuration:
- **`apps/`**: FastAPI application for Slack and GitHub app setup
  - Guides users through OAuth flows
  - Generates app manifests and configurations
  - Stores credentials securely

### `channel` module

Defines request handlers for user interactions:
- **`RequestHandler`**: Abstract base for handling permission and feedback requests
- **`RichConsoleHandler`**: Terminal UI implementation using Rich library
- **`SlackChannelHandler`**: Slack-specific ephemeral message handler
- **`WebSocketHandler`**: WebSocket-based handler for web interfaces
