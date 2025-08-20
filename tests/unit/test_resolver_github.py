from unittest.mock import MagicMock, patch

import pytest

from hygroup.gateway.github import GithubGateway
from hygroup.session import SessionManager


@pytest.fixture
def session_manager():
    """Create a mock session manager for testing."""
    manager = MagicMock(spec=SessionManager)
    return manager


@pytest.fixture
def github_gateway(session_manager):
    """Create a GithubGateway instance with test user mappings."""
    user_mapping = {
        "bot": "bot",
        "user": "john",
        "user1": "alice",
        "user2": "bob",
        "support": "team",
        "admin": "administrator",
        "assistant": "assistant",
    }

    # Mock GitHub integration components to avoid real GitHub connections
    with (
        patch("hygroup.gateway.github.gateway.Auth"),
        patch("hygroup.gateway.github.gateway.GithubIntegration"),
        patch("hygroup.gateway.github.gateway.GithubService"),
        patch("hygroup.gateway.github.gateway.create_app"),
        patch("hygroup.gateway.github.gateway.uvicorn.Config"),
        patch("hygroup.gateway.github.gateway.uvicorn.Server"),
    ):
        gateway = GithubGateway(
            session_manager=session_manager,
            github_app_id=12345,
            github_installation_id=67890,
            github_private_key="test-private-key",
            github_app_username="test-bot",
            user_mapping=user_mapping,
        )
        return gateway


class TestGithubResolveMentions:
    """Test GithubGateway._resolve_mentions method for GitHub-specific mention formats."""

    def test_basic_username_format(self, github_gateway):
        """Test basic @username format resolution."""
        assert github_gateway._resolve_mentions("@user") == "@john"
        assert github_gateway._resolve_mentions("@user1") == "@alice"
        assert github_gateway._resolve_mentions("@user2") == "@bob"

    def test_username_in_context(self, github_gateway):
        """Test @username mentions within text."""
        assert github_gateway._resolve_mentions("blah @bot blah") == "blah @bot blah"
        assert github_gateway._resolve_mentions("@user hello") == "@john hello"
        assert github_gateway._resolve_mentions("hello @user") == "hello @john"
        assert github_gateway._resolve_mentions("hello @user!") == "hello @john!"

    def test_multiple_mentions(self, github_gateway):
        """Test multiple @username mentions in one message."""
        assert github_gateway._resolve_mentions("@user1 and @user2") == "@alice and @bob"
        assert github_gateway._resolve_mentions("@bot please help @user") == "@bot please help @john"
        assert github_gateway._resolve_mentions("@user ping @bot") == "@john ping @bot"

    def test_unknown_users(self, github_gateway):
        """Test @username mentions for users not in mapping."""
        assert github_gateway._resolve_mentions("hello @unknown") == "hello @unknown"
        assert github_gateway._resolve_mentions("@unknown user") == "@unknown user"
        assert github_gateway._resolve_mentions("@user1 hello @unknown") == "@alice hello @unknown"

    def test_empty_and_none_cases(self, github_gateway):
        """Test empty and None inputs."""
        assert github_gateway._resolve_mentions("") == ""
        assert github_gateway._resolve_mentions(None) == ""
        assert github_gateway._resolve_mentions("no mentions here") == "no mentions here"

    def test_word_boundary_detection(self, github_gateway):
        """Test that @ preceded by word characters is not matched."""
        # Emails should not be matched due to word boundary detection
        assert github_gateway._resolve_mentions("email@example.com") == "email@example.com"
        assert github_gateway._resolve_mentions("test@domain.org") == "test@domain.org"

        # Double @ - second @ should match as it's not preceded by word char
        assert github_gateway._resolve_mentions("@@user") == "@@john"

        # @ alone or with non-username chars
        assert github_gateway._resolve_mentions("@") == "@"
        assert github_gateway._resolve_mentions("@ ") == "@ "

    def test_emails_remain_intact(self, github_gateway):
        """Test that email addresses are not modified."""
        assert github_gateway._resolve_mentions("first.last@example.com") == "first.last@example.com"
        assert github_gateway._resolve_mentions("user+tag@domain.co.uk") == "user+tag@domain.co.uk"
        assert github_gateway._resolve_mentions("test@sub.domain.org") == "test@sub.domain.org"
        assert github_gateway._resolve_mentions("admin@company-name.com") == "admin@company-name.com"
        assert github_gateway._resolve_mentions("123@numbers.net") == "123@numbers.net"

    def test_mixed_emails_and_mentions(self, github_gateway):
        """Test text containing both emails and GitHub mentions."""
        assert (
            github_gateway._resolve_mentions("Contact @support at help@company.com")
            == "Contact @team at help@company.com"
        )
        assert (
            github_gateway._resolve_mentions("Email me@company.com or ping @admin")
            == "Email me@company.com or ping @administrator"
        )
        assert (
            github_gateway._resolve_mentions("@bot please send to user@domain.com")
            == "@bot please send to user@domain.com"
        )

    def test_multiple_emails_in_text(self, github_gateway):
        """Test multiple emails remain intact."""
        assert (
            github_gateway._resolve_mentions("Send to admin@company.com and user@domain.org")
            == "Send to admin@company.com and user@domain.org"
        )

    def test_emails_in_various_contexts(self, github_gateway):
        """Test emails in different surrounding contexts."""
        assert github_gateway._resolve_mentions("(user@example.com)") == "(user@example.com)"
        assert github_gateway._resolve_mentions("[admin@company.com]") == "[admin@company.com]"
        assert github_gateway._resolve_mentions("'test@domain.org'") == "'test@domain.org'"
        assert github_gateway._resolve_mentions('"contact@company.com"') == '"contact@company.com"'

    def test_whitespace_preservation(self, github_gateway):
        """Test that whitespace is preserved correctly."""
        assert github_gateway._resolve_mentions("  @user  ") == "  @john  "
        assert github_gateway._resolve_mentions("\t@user1\n") == "\t@alice\n"
        assert github_gateway._resolve_mentions("@user1\n\n@user2") == "@alice\n\n@bob"

    def test_special_characters_around_mentions(self, github_gateway):
        """Test mentions with special characters in surrounding text."""
        assert github_gateway._resolve_mentions("!@user!") == "!@john!"
        assert github_gateway._resolve_mentions("#@user1$") == "#@alice$"
        assert github_gateway._resolve_mentions("(@user)") == "(@john)"
        assert github_gateway._resolve_mentions("[@user2]") == "[@bob]"
        assert github_gateway._resolve_mentions("'@bot'") == "'@bot'"
        assert github_gateway._resolve_mentions('"@admin"') == '"@administrator"'

    def test_complex_message_with_multiple_elements(self, github_gateway):
        """Test complex message with multiple mentions and various text elements."""
        text = "Hey @bot, can you help @user1 and @user2 with @unknown?"
        expected = "Hey @bot, can you help @alice and @bob with @unknown?"
        assert github_gateway._resolve_mentions(text) == expected

    def test_username_with_hyphens(self, github_gateway):
        """Test that usernames with hyphens are handled correctly."""
        # Add users with hyphens (common in GitHub usernames)
        github_gateway._github_user_mapping["user-test"] = "testuser"
        github_gateway._github_user_mapping["bot-name"] = "botname"
        github_gateway._system_user_mapping["testuser"] = "user-test"
        github_gateway._system_user_mapping["botname"] = "bot-name"

        assert github_gateway._resolve_mentions("@user-test") == "@testuser"
        assert github_gateway._resolve_mentions("Hello @bot-name!") == "Hello @botname!"
        assert github_gateway._resolve_mentions("@user-test and @bot-name") == "@testuser and @botname"

    def test_receiver_prefix_removal(self, github_gateway):
        """Test removal of receiver prefix in mentions with slash notation."""
        # The _remove_receiver_prefix is called within _resolve_mentions
        # Set up the gateway with a specific app username
        github_gateway._github_app_username = "test-bot"

        # Add mapping for sub-users (after prefix removal)
        github_gateway._github_user_mapping["subuser"] = "resolved_subuser"
        github_gateway._github_user_mapping["agent1"] = "agent_one"
        github_gateway._github_user_mapping["helper"] = "helper_bot"

        # Test that test-bot/subuser gets resolved properly
        # The pattern matches @test-bot/subuser, removes "test-bot/" prefix, resolves "subuser"
        assert github_gateway._resolve_mentions("@test-bot/subuser") == "@resolved_subuser"
        assert github_gateway._resolve_mentions("@test-bot/agent1") == "@agent_one"
        assert github_gateway._resolve_mentions("Hello @test-bot/helper!") == "Hello @helper_bot!"

        # Regular mentions should still work
        assert github_gateway._resolve_mentions("@user") == "@john"
        assert github_gateway._resolve_mentions("@admin") == "@administrator"

        # Mentions with slash but different prefix should not be affected
        assert github_gateway._resolve_mentions("@other/user") == "@other/user"
