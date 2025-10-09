import pytest

from hygroup.gateway.github import GithubGateway


@pytest.fixture
def user_mapping():
    """Create a user mapping for testing."""
    return {
        "bot": "bot",
        "user": "john",
        "user1": "alice",
        "user2": "bob",
        "support": "team",
        "admin": "administrator",
        "assistant": "assistant",
    }


@pytest.fixture
def resolver(user_mapping):
    """Create a resolver function based on user mapping."""

    def resolve(username: str) -> str:
        return user_mapping.get(username, username)

    return resolve


class TestGithubResolveMentions:
    """Test GithubGateway.resolve_mentions static method for GitHub-specific mention formats."""

    def test_basic_username_format(self, resolver):
        """Test basic @username format resolution."""
        assert GithubGateway.resolve_mentions("@user", resolver) == "@john"
        assert GithubGateway.resolve_mentions("@user1", resolver) == "@alice"
        assert GithubGateway.resolve_mentions("@user2", resolver) == "@bob"

    def test_username_in_context(self, resolver):
        """Test @username mentions within text."""
        assert GithubGateway.resolve_mentions("blah @bot blah", resolver) == "blah @bot blah"
        assert GithubGateway.resolve_mentions("@user hello", resolver) == "@john hello"
        assert GithubGateway.resolve_mentions("hello @user", resolver) == "hello @john"
        assert GithubGateway.resolve_mentions("hello @user!", resolver) == "hello @john!"

    def test_multiple_mentions(self, resolver):
        """Test multiple @username mentions in one message."""
        assert GithubGateway.resolve_mentions("@user1 and @user2", resolver) == "@alice and @bob"
        assert GithubGateway.resolve_mentions("@bot please help @user", resolver) == "@bot please help @john"
        assert GithubGateway.resolve_mentions("@user ping @bot", resolver) == "@john ping @bot"

    def test_unknown_users(self, resolver):
        """Test @username mentions for users not in mapping."""
        assert GithubGateway.resolve_mentions("hello @unknown", resolver) == "hello @unknown"
        assert GithubGateway.resolve_mentions("@unknown user", resolver) == "@unknown user"
        assert GithubGateway.resolve_mentions("@user1 hello @unknown", resolver) == "@alice hello @unknown"

    def test_empty_cases(self, resolver):
        """Test empty inputs."""
        assert GithubGateway.resolve_mentions("", resolver) == ""
        assert GithubGateway.resolve_mentions("no mentions here", resolver) == "no mentions here"

    def test_word_boundary_detection(self, resolver):
        """Test that @ preceded by word characters is not matched."""
        # Emails should not be matched due to word boundary detection
        assert GithubGateway.resolve_mentions("email@example.com", resolver) == "email@example.com"
        assert GithubGateway.resolve_mentions("test@domain.org", resolver) == "test@domain.org"

        # Double @ - second @ should match as it's not preceded by word char
        assert GithubGateway.resolve_mentions("@@user", resolver) == "@@john"

        # @ alone or with non-username chars
        assert GithubGateway.resolve_mentions("@", resolver) == "@"
        assert GithubGateway.resolve_mentions("@ ", resolver) == "@ "

    def test_emails_remain_intact(self, resolver):
        """Test that email addresses are not modified."""
        assert GithubGateway.resolve_mentions("first.last@example.com", resolver) == "first.last@example.com"
        assert GithubGateway.resolve_mentions("user+tag@domain.co.uk", resolver) == "user+tag@domain.co.uk"
        assert GithubGateway.resolve_mentions("test@sub.domain.org", resolver) == "test@sub.domain.org"
        assert GithubGateway.resolve_mentions("admin@company-name.com", resolver) == "admin@company-name.com"
        assert GithubGateway.resolve_mentions("123@numbers.net", resolver) == "123@numbers.net"

    def test_mixed_emails_and_mentions(self, resolver):
        """Test text containing both emails and GitHub mentions."""
        assert (
            GithubGateway.resolve_mentions("Contact @support at help@company.com", resolver)
            == "Contact @team at help@company.com"
        )
        assert (
            GithubGateway.resolve_mentions("Email me@company.com or ping @admin", resolver)
            == "Email me@company.com or ping @administrator"
        )
        assert (
            GithubGateway.resolve_mentions("@bot please send to user@domain.com", resolver)
            == "@bot please send to user@domain.com"
        )

    def test_multiple_emails_in_text(self, resolver):
        """Test multiple emails remain intact."""
        assert (
            GithubGateway.resolve_mentions("Send to admin@company.com and user@domain.org", resolver)
            == "Send to admin@company.com and user@domain.org"
        )

    def test_emails_in_various_contexts(self, resolver):
        """Test emails in different surrounding contexts."""
        assert GithubGateway.resolve_mentions("(user@example.com)", resolver) == "(user@example.com)"
        assert GithubGateway.resolve_mentions("[admin@company.com]", resolver) == "[admin@company.com]"
        assert GithubGateway.resolve_mentions("'test@domain.org'", resolver) == "'test@domain.org'"
        assert GithubGateway.resolve_mentions('"contact@company.com"', resolver) == '"contact@company.com"'

    def test_whitespace_preservation(self, resolver):
        """Test that whitespace is preserved correctly."""
        assert GithubGateway.resolve_mentions("  @user  ", resolver) == "  @john  "
        assert GithubGateway.resolve_mentions("\t@user1\n", resolver) == "\t@alice\n"
        assert GithubGateway.resolve_mentions("@user1\n\n@user2", resolver) == "@alice\n\n@bob"

    def test_special_characters_around_mentions(self, resolver):
        """Test mentions with special characters in surrounding text."""
        assert GithubGateway.resolve_mentions("!@user!", resolver) == "!@john!"
        assert GithubGateway.resolve_mentions("#@user1$", resolver) == "#@alice$"
        assert GithubGateway.resolve_mentions("(@user)", resolver) == "(@john)"
        assert GithubGateway.resolve_mentions("[@user2]", resolver) == "[@bob]"
        assert GithubGateway.resolve_mentions("'@bot'", resolver) == "'@bot'"
        assert GithubGateway.resolve_mentions('"@admin"', resolver) == '"@administrator"'

    def test_complex_message_with_multiple_elements(self, resolver):
        """Test complex message with multiple mentions and various text elements."""
        text = "Hey @bot, can you help @user1 and @user2 with @unknown?"
        expected = "Hey @bot, can you help @alice and @bob with @unknown?"
        assert GithubGateway.resolve_mentions(text, resolver) == expected

    def test_username_with_hyphens(self, user_mapping, resolver):
        """Test that usernames with hyphens are handled correctly."""
        # Add users with hyphens (common in GitHub usernames)
        user_mapping["user-test"] = "testuser"
        user_mapping["bot-name"] = "botname"

        assert GithubGateway.resolve_mentions("@user-test", resolver) == "@testuser"
        assert GithubGateway.resolve_mentions("Hello @bot-name!", resolver) == "Hello @botname!"
        assert GithubGateway.resolve_mentions("@user-test and @bot-name", resolver) == "@testuser and @botname"

    def test_slash_notation_in_mentions(self, user_mapping, resolver):
        """Test mentions with slash notation like @bot/agent."""
        # Add mappings for slash-notation users
        user_mapping["bot/subuser"] = "resolved_subuser"
        user_mapping["bot/agent1"] = "agent_one"
        user_mapping["bot/helper"] = "helper_bot"

        assert GithubGateway.resolve_mentions("@bot/subuser", resolver) == "@resolved_subuser"
        assert GithubGateway.resolve_mentions("@bot/agent1", resolver) == "@agent_one"
        assert GithubGateway.resolve_mentions("Hello @bot/helper!", resolver) == "Hello @helper_bot!"

        # Regular mentions should still work
        assert GithubGateway.resolve_mentions("@user", resolver) == "@john"
        assert GithubGateway.resolve_mentions("@admin", resolver) == "@administrator"

        # Mentions with slash but not in mapping should remain unchanged
        assert GithubGateway.resolve_mentions("@other/user", resolver) == "@other/user"
