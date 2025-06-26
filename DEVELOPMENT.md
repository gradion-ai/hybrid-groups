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

## Web management interface

The project includes a web-based management interface. To set it up:

### Prerequisites

Install Node.js 20.x (LTS version) from the [official website](https://nodejs.org/). Verify installation:

```bash
node --version
npm --version
```

### Setup

Navigate to the `web` directory and configure the environment:

```bash
cd web
cp .env.development.example .env.development
cp .env.production.example .env.production
```

Install dependencies:

```bash
npm install
```

### Run the web UI

Start the development server:

```bash
npm run dev
```

The web interface will be available at http://localhost:3000

### Run the web API

The web interface uses the API implemented in [hygroup/api](hygroup/api/). Start the API server using:

```bash
python examples/app_server.py --user-registry ...
```

### Code quality checks

Enforce coding conventions and check for Typescript errors:

```bash
# Code linting
npm run lint

# TypeScript compilation check
npx tsc --noEmit
```
