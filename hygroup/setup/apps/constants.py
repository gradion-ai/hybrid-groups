from pathlib import Path


class Paths:
    ROOT = Path(__file__).parent
    STATIC = ROOT / "static"

    SETUP_GITHUB_TEMPLATE = STATIC / "setup-github-app.html"
    GITHUB_SUCCESS_TEMPLATE = STATIC / "github-success.html"
    GITHUB_ERROR_TEMPLATE = STATIC / "github-error.html"

    SETUP_SLACK_TEMPLATE = STATIC / "setup-slack-app.html"


class Routes:
    API_PREFIX = "/api/v1"

    GITHUB_APP = "/github-app"
    GITHUB_MANIFEST = f"{API_PREFIX}/github-app/manifest"
    GITHUB_CALLBACK = f"{API_PREFIX}/github-app/callback"
    GITHUB_COMPLETE = f"{API_PREFIX}/github-app/complete"

    SLACK_APP = "/slack-app"
    SLACK_CREATE = f"{API_PREFIX}/slack-app/create"
    SLACK_COMPLETE = f"{API_PREFIX}/slack-app/complete"
