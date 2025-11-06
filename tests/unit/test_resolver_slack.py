import pytest

from hygroup.gateway.slack import SlackGateway


@pytest.fixture
def user_mapping():
    """Create a user mapping for testing."""
    return {
        "U04P0E9BQ73": "martin",
        "U123": "alice",
        "U456": "bob",
        "UBOT": "bot",
        "UASSIST": "assistant",
    }


@pytest.fixture
def resolver(user_mapping):
    """Create a resolver function based on user mapping."""

    def resolve(user_id: str) -> str:
        return user_mapping.get(user_id, user_id)

    return resolve


class TestSlackResolverMentions:
    """Test SlackGateway.resolve_mentions static method for Slack-specific mention formats."""

    def test_basic_slack_userid_format(self, resolver):
        """Test basic <@userid> format resolution."""
        assert SlackGateway.resolve_mentions("<@U04P0E9BQ73>", resolver) == "@martin"
        assert SlackGateway.resolve_mentions("<@U123>", resolver) == "@alice"
        assert SlackGateway.resolve_mentions("<@U456>", resolver) == "@bob"

    def test_slack_userid_in_context(self, resolver):
        """Test <@userid> mentions within text."""
        assert SlackGateway.resolve_mentions("blah <@U04P0E9BQ73> blah", resolver) == "blah @martin blah"
        assert SlackGateway.resolve_mentions("<@U123> hello", resolver) == "@alice hello"
        assert SlackGateway.resolve_mentions("hello <@U456>", resolver) == "hello @bob"

    def test_multiple_slack_mentions(self, resolver):
        """Test multiple <@userid> mentions in one message."""
        assert SlackGateway.resolve_mentions("<@U123> and <@U456>", resolver) == "@alice and @bob"
        assert SlackGateway.resolve_mentions("<@UBOT> please help <@U123>", resolver) == "@bot please help @alice"
        assert SlackGateway.resolve_mentions("<@U123> ping <@UBOT>", resolver) == "@alice ping @bot"

    def test_unknown_slack_users(self, resolver):
        """Test <@userid> mentions for users not in mapping."""
        assert SlackGateway.resolve_mentions("hello <@U999>", resolver) == "hello @U999"
        assert SlackGateway.resolve_mentions("<@UNKNOWN>", resolver) == "@UNKNOWN"
        assert SlackGateway.resolve_mentions("<@U123> hello <@U999>", resolver) == "@alice hello @U999"

    def test_empty_cases(self, resolver):
        """Test empty inputs."""
        assert SlackGateway.resolve_mentions("", resolver) == ""
        assert SlackGateway.resolve_mentions("no mentions here", resolver) == "no mentions here"

    def test_malformed_slack_mentions(self, resolver):
        """Test malformed mention patterns that should not match."""
        assert SlackGateway.resolve_mentions("<@>", resolver) == "<@>"  # Empty brackets
        assert SlackGateway.resolve_mentions("@U123", resolver) == "@U123"  # Missing brackets
        assert SlackGateway.resolve_mentions("<U123>", resolver) == "<U123>"  # Missing @
        assert SlackGateway.resolve_mentions("< @U123>", resolver) == "< @U123>"  # Space after <

    def test_emails_remain_intact(self, resolver):
        """Test that email addresses are not modified."""
        assert SlackGateway.resolve_mentions("first.last@example.com", resolver) == "first.last@example.com"
        assert SlackGateway.resolve_mentions("user+tag@domain.co.uk", resolver) == "user+tag@domain.co.uk"
        assert SlackGateway.resolve_mentions("test@sub.domain.org", resolver) == "test@sub.domain.org"
        assert SlackGateway.resolve_mentions("admin@company-name.com", resolver) == "admin@company-name.com"

    def test_mixed_emails_and_mentions(self, resolver):
        """Test text containing both emails and Slack mentions."""
        assert (
            SlackGateway.resolve_mentions("Contact <@UASSIST> at help@company.com", resolver)
            == "Contact @assistant at help@company.com"
        )
        assert (
            SlackGateway.resolve_mentions("Email me@company.com or ping <@U123>", resolver)
            == "Email me@company.com or ping @alice"
        )
        assert (
            SlackGateway.resolve_mentions("<@UBOT> please send to user@domain.com", resolver)
            == "@bot please send to user@domain.com"
        )

    def test_whitespace_preservation(self, resolver):
        """Test that whitespace is preserved correctly."""
        assert SlackGateway.resolve_mentions("  <@U123>  ", resolver) == "  @alice  "
        assert SlackGateway.resolve_mentions("\t<@U456>\n", resolver) == "\t@bob\n"
        assert SlackGateway.resolve_mentions("<@U123>\n\n<@U456>", resolver) == "@alice\n\n@bob"

    def test_special_characters_around_mentions(self, resolver):
        """Test mentions with special characters in surrounding text."""
        assert SlackGateway.resolve_mentions("!<@U123>!", resolver) == "!@alice!"
        assert SlackGateway.resolve_mentions("#<@U456>$", resolver) == "#@bob$"
        assert SlackGateway.resolve_mentions("(<@UBOT>)", resolver) == "(@bot)"
        assert SlackGateway.resolve_mentions("[<@U123>]", resolver) == "[@alice]"
        assert SlackGateway.resolve_mentions("'<@U456>'", resolver) == "'@bob'"
        assert SlackGateway.resolve_mentions('"<@UBOT>"', resolver) == '"@bot"'

    def test_complex_message_with_multiple_elements(self, resolver):
        """Test complex message with multiple mentions and various text elements."""
        text = "Hey <@UBOT>, can you help <@U123> and <@U456> with <@U999>?"
        expected = "Hey @bot, can you help @alice and @bob with @U999?"
        assert SlackGateway.resolve_mentions(text, resolver) == expected

    def test_slack_userid_with_special_chars(self, user_mapping, resolver):
        """Test that user IDs with slashes and hyphens are handled correctly."""
        # Add a user with special characters in the ID
        user_mapping["U-TEST/123"] = "testuser"

        assert SlackGateway.resolve_mentions("<@U-TEST/123>", resolver) == "@testuser"
        assert SlackGateway.resolve_mentions("Hello <@U-TEST/123>!", resolver) == "Hello @testuser!"
