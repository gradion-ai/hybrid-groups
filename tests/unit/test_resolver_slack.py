from unittest.mock import MagicMock, patch

import pytest

from hygroup.connect import ComposioConnector
from hygroup.gateway.slack import SlackGateway
from hygroup.session import SessionManager


@pytest.fixture
def session_manager():
    """Create a mock session manager for testing."""
    manager = MagicMock(spec=SessionManager)
    manager.request_handler = MagicMock()
    return manager


@pytest.fixture
def composio_connector():
    """Create a mock composio connector for testing."""
    connector = MagicMock(spec=ComposioConnector)
    return connector


@pytest.fixture
def slack_gateway(session_manager, composio_connector, monkeypatch):
    """Create a SlackGateway instance with test user mappings."""
    # Set required environment variables
    monkeypatch.setenv("SLACK_BOT_TOKEN", "test-bot-token")
    monkeypatch.setenv("SLACK_APP_TOKEN", "test-app-token")

    user_mapping = {
        "U04P0E9BQ73": "martin",
        "U123": "alice",
        "U456": "bob",
        "UBOT": "bot",
        "UASSIST": "assistant",
    }

    # Mock the AsyncApp and AsyncSocketModeHandler to avoid real Slack connections
    with (
        patch("hygroup.gateway.slack.gateway.AsyncApp"),
        patch("hygroup.gateway.slack.gateway.AsyncWebClient"),
        patch("hygroup.gateway.slack.gateway.AsyncSocketModeHandler"),
    ):
        gateway = SlackGateway(
            session_manager=session_manager,
            composio_connector=composio_connector,
            user_mapping=user_mapping,
            handle_permission_requests=False,
        )
        return gateway


class TestSlackResolverMentions:
    """Test SlackGateway._resolve_mentions method for Slack-specific mention formats."""

    def test_basic_slack_userid_format(self, slack_gateway):
        """Test basic <@userid> format resolution."""
        assert slack_gateway._resolve_mentions("<@U04P0E9BQ73>") == "@martin"
        assert slack_gateway._resolve_mentions("<@U123>") == "@alice"
        assert slack_gateway._resolve_mentions("<@U456>") == "@bob"

    def test_slack_userid_in_context(self, slack_gateway):
        """Test <@userid> mentions within text."""
        assert slack_gateway._resolve_mentions("blah <@U04P0E9BQ73> blah") == "blah @martin blah"
        assert slack_gateway._resolve_mentions("<@U123> hello") == "@alice hello"
        assert slack_gateway._resolve_mentions("hello <@U456>") == "hello @bob"

    def test_multiple_slack_mentions(self, slack_gateway):
        """Test multiple <@userid> mentions in one message."""
        assert slack_gateway._resolve_mentions("<@U123> and <@U456>") == "@alice and @bob"
        assert slack_gateway._resolve_mentions("<@UBOT> please help <@U123>") == "@bot please help @alice"
        assert slack_gateway._resolve_mentions("<@U123> ping <@UBOT>") == "@alice ping @bot"

    def test_unknown_slack_users(self, slack_gateway):
        """Test <@userid> mentions for users not in mapping."""
        assert slack_gateway._resolve_mentions("hello <@U999>") == "hello @U999"
        assert slack_gateway._resolve_mentions("<@UNKNOWN>") == "@UNKNOWN"
        assert slack_gateway._resolve_mentions("<@U123> hello <@U999>") == "@alice hello @U999"

    def test_empty_and_none_cases(self, slack_gateway):
        """Test empty and None inputs."""
        assert slack_gateway._resolve_mentions("") == ""
        assert slack_gateway._resolve_mentions(None) == ""
        assert slack_gateway._resolve_mentions("no mentions here") == "no mentions here"

    def test_malformed_slack_mentions(self, slack_gateway):
        """Test malformed mention patterns that should not match."""
        assert slack_gateway._resolve_mentions("<@>") == "<@>"  # Empty brackets
        assert slack_gateway._resolve_mentions("@U123") == "@U123"  # Missing brackets
        assert slack_gateway._resolve_mentions("<U123>") == "<U123>"  # Missing @
        assert slack_gateway._resolve_mentions("< @U123>") == "< @U123>"  # Space after <

    def test_emails_remain_intact(self, slack_gateway):
        """Test that email addresses are not modified."""
        assert slack_gateway._resolve_mentions("first.last@example.com") == "first.last@example.com"
        assert slack_gateway._resolve_mentions("user+tag@domain.co.uk") == "user+tag@domain.co.uk"
        assert slack_gateway._resolve_mentions("test@sub.domain.org") == "test@sub.domain.org"
        assert slack_gateway._resolve_mentions("admin@company-name.com") == "admin@company-name.com"

    def test_mixed_emails_and_mentions(self, slack_gateway):
        """Test text containing both emails and Slack mentions."""
        assert (
            slack_gateway._resolve_mentions("Contact <@UASSIST> at help@company.com")
            == "Contact @assistant at help@company.com"
        )
        assert (
            slack_gateway._resolve_mentions("Email me@company.com or ping <@U123>")
            == "Email me@company.com or ping @alice"
        )
        assert (
            slack_gateway._resolve_mentions("<@UBOT> please send to user@domain.com")
            == "@bot please send to user@domain.com"
        )

    def test_whitespace_preservation(self, slack_gateway):
        """Test that whitespace is preserved correctly."""
        assert slack_gateway._resolve_mentions("  <@U123>  ") == "  @alice  "
        assert slack_gateway._resolve_mentions("\t<@U456>\n") == "\t@bob\n"
        assert slack_gateway._resolve_mentions("<@U123>\n\n<@U456>") == "@alice\n\n@bob"

    def test_special_characters_around_mentions(self, slack_gateway):
        """Test mentions with special characters in surrounding text."""
        assert slack_gateway._resolve_mentions("!<@U123>!") == "!@alice!"
        assert slack_gateway._resolve_mentions("#<@U456>$") == "#@bob$"
        assert slack_gateway._resolve_mentions("(<@UBOT>)") == "(@bot)"
        assert slack_gateway._resolve_mentions("[<@U123>]") == "[@alice]"
        assert slack_gateway._resolve_mentions("'<@U456>'") == "'@bob'"
        assert slack_gateway._resolve_mentions('"<@UBOT>"') == '"@bot"'

    def test_complex_message_with_multiple_elements(self, slack_gateway):
        """Test complex message with multiple mentions and various text elements."""
        text = "Hey <@UBOT>, can you help <@U123> and <@U456> with <@U999>?"
        expected = "Hey @bot, can you help @alice and @bob with @U999?"
        assert slack_gateway._resolve_mentions(text) == expected

    def test_slack_userid_with_special_chars(self, slack_gateway):
        """Test that user IDs with slashes and hyphens are handled correctly."""
        # Add a user with special characters in the ID
        slack_gateway._slack_user_mapping["U-TEST/123"] = "testuser"
        slack_gateway._system_user_mapping["testuser"] = "U-TEST/123"

        assert slack_gateway._resolve_mentions("<@U-TEST/123>") == "@testuser"
        assert slack_gateway._resolve_mentions("Hello <@U-TEST/123>!") == "Hello @testuser!"
