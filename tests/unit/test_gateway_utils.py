import pytest

from hygroup.gateway.utils import (
    extract_initial_mention,
    resolve_mentions,
)


@pytest.mark.parametrize(
    "text, expected_name, expected_remaining",
    [
        ("@user1 hello world", "user1", "hello world"),
        ("<@user2> foo bar", "user2", "foo bar"),
        ("  @user-3  baz", "user-3", "baz"),
        (" <@user-4>   qux", "user-4", "qux"),
        ("@user5", "user5", ""),
        ("<@user6>", "user6", ""),
        ("no mention here", None, "no mention here"),
        ("", None, ""),
        ("   ", None, "   "),
        ("  @user7", "user7", ""),
        ("<@user8>  ", "user8", ""),
        ("  <@user-9>text", "user-9", "text"),
        ("@user10text", "user10text", ""),  # This is current behavior, name can be followed by text without space
        ("<@user11text>", "user11text", ""),  # This is current behavior
    ],
)
def test_extract_mention(text, expected_name, expected_remaining):
    name, remaining = extract_initial_mention(text)
    assert name == expected_name
    assert remaining == expected_remaining


# Test case for when the regex matches but it's not the intended pattern (e.g. email)
# This should ideally not be matched if we only want @mentions or <@mentions>
# Current regex might capture 'user' from 'user@example.com' if we are not careful
# However, the current regex is anchored to the beginning of the string (^)
# and expects either @name or <@name>, so it should be fine.


def test_extract_mention_no_match_for_email_like_strings():
    text = "user@example.com some text"
    name, remaining = extract_initial_mention(text)
    assert name is None
    assert remaining == text


def test_extract_mention_with_special_chars_in_remaining_text():
    text = "@user1 !@#$%^&*()_+"
    name, remaining = extract_initial_mention(text)
    assert name == "user1"
    assert remaining == "!@#$%^&*()_+"

    text = "<@user2> !@#$%^&*()_+"
    name, remaining = extract_initial_mention(text)
    assert name == "user2"
    assert remaining == "!@#$%^&*()_+"


@pytest.mark.parametrize(
    "text,resolver_mapping,expected",
    [
        # Basic @username format
        ("blah @bot blah", {"bot": "bot"}, "blah bot blah"),
        ("@user hello", {"user": "john"}, "john hello"),
        ("hello @user", {"user": "john"}, "hello john"),
        # Basic <@userid> format
        ("blah <@U04P0E9BQ73> blah", {"U04P0E9BQ73": "martin"}, "blah martin blah"),
        ("<@U123> hello", {"U123": "alice"}, "alice hello"),
        ("hello <@U456>", {"U456": "bob"}, "hello bob"),
        # Multiple mentions
        ("@user1 and @user2", {"user1": "alice", "user2": "bob"}, "alice and bob"),
        ("<@U123> and <@U456>", {"U123": "alice", "U456": "bob"}, "alice and bob"),
        ("@bot please help <@U123>", {"bot": "assistant", "U123": "user"}, "assistant please help user"),
        # Mixed formats
        ("@bot help <@U123>", {"bot": "assistant", "U123": "john"}, "assistant help john"),
        ("<@U123> ping @bot", {"U123": "john", "bot": "assistant"}, "john ping assistant"),
        # Unknown users (not in mapping)
        ("hello <@U999>", {}, "hello U999"),
        ("@unknown user", {}, "unknown user"),
        ("<@U123> hello <@U456>", {"U123": "alice"}, "alice hello U456"),
        # Empty and None cases
        ("", {}, ""),
        ("no mentions here", {}, "no mentions here"),
        # Edge cases
        ("@@double", {}, "@double"),  # Double @ should leave one @
        ("email@example.com", {}, "emailexample.com"),  # @ in email gets removed
        ("@", {}, "@"),  # Single @ with nothing after (no match)
        ("<@>", {}, "<@>"),  # Empty brackets (no match)
        # Multiple mentions in complex text
        (
            "Hey @bot, can you help @user1 and @user2 with <@U123>?",
            {"bot": "assistant", "user1": "alice", "user2": "bob", "U123": "charlie"},
            "Hey assistant, can you help alice and bob with charlie?",
        ),
    ],
)
def test_replace_all_mentions(text, resolver_mapping, expected):
    """Test replace_all_mentions with various mention formats."""

    def resolver(user_id):
        return resolver_mapping.get(user_id, user_id)

    result = resolve_mentions(text, resolver)
    assert result == expected


def test_replace_all_mentions_with_none_text():
    """Test that None text returns empty string."""

    def resolver(user_id):
        return user_id

    # The function checks for falsy values and returns the input
    assert resolve_mentions(None, resolver) is None
    assert resolve_mentions("", resolver) == ""


def test_replace_all_mentions_preserves_whitespace():
    """Test that whitespace is preserved correctly."""

    def resolver(user_id):
        return "resolved"

    assert resolve_mentions("  @user  ", resolver) == "  resolved  "
    assert resolve_mentions("\t<@U123>\n", resolver) == "\tresolved\n"
    assert resolve_mentions("@user1\n\n@user2", resolver) == "resolved\n\nresolved"


def test_replace_all_mentions_with_special_characters():
    """Test mentions with special characters in surrounding text."""
    resolver_mapping = {"user": "john", "U123": "alice"}

    def resolver(user_id):
        return resolver_mapping.get(user_id, user_id)

    assert resolve_mentions("!@user!", resolver) == "!john!"
    assert resolve_mentions("#<@U123>$", resolver) == "#alice$"
    assert resolve_mentions("(@user)", resolver) == "(john)"
    assert resolve_mentions("[<@U123>]", resolver) == "[alice]"
