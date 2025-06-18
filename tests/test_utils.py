import pytest

from hygroup.agent.default.utils import resolve_config_variables
from hygroup.gateway.utils import (
    extract_mention,
    extract_thread_references,
    replace_all_mentions,
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
    name, remaining = extract_mention(text)
    assert name == expected_name
    assert remaining == expected_remaining


# Test case for when the regex matches but it's not the intended pattern (e.g. email)
# This should ideally not be matched if we only want @mentions or <@mentions>
# Current regex might capture 'user' from 'user@example.com' if we are not careful
# However, the current regex is anchored to the beginning of the string (^)
# and expects either @name or <@name>, so it should be fine.


def test_extract_mention_no_match_for_email_like_strings():
    text = "user@example.com some text"
    name, remaining = extract_mention(text)
    assert name is None
    assert remaining == text


def test_extract_mention_with_special_chars_in_remaining_text():
    text = "@user1 !@#$%^&*()_+"
    name, remaining = extract_mention(text)
    assert name == "user1"
    assert remaining == "!@#$%^&*()_+"

    text = "<@user2> !@#$%^&*()_+"
    name, remaining = extract_mention(text)
    assert name == "user2"
    assert remaining == "!@#$%^&*()_+"


@pytest.mark.parametrize(
    "text, expected_references",
    [
        ("thread:123.215", ["123.215"]),
        ("thread:f2a-3b7", ["f2a-3b7"]),
        ("thread:123.215 and thread:f2a-3b7", ["123.215", "f2a-3b7"]),
        ("Check thread:abc123 for details", ["abc123"]),
        ("Multiple: thread:first.1 thread:second-2 thread:third.3-4", ["first.1", "second-2", "third.3-4"]),
        ("thread:simple", ["simple"]),
        ("thread:with.dots.123", ["with.dots.123"]),
        ("thread:with-hyphens-456", ["with-hyphens-456"]),
        ("thread:mixed.123-abc.def", ["mixed.123-abc.def"]),
        ("No session references here", []),
        ("", []),
        ("thread: missing identifier", []),  # Empty identifier after colon
        ("threadmissing colon", []),  # Missing colon
        ("This thread:123 and that thread:456.789", ["123", "456.789"]),
        ("thread:a1b2c3", ["a1b2c3"]),
        ("Prefix thread:test suffix", ["test"]),
    ],
)
def test_extract_session_references(text, expected_references):
    references = extract_thread_references(text)
    assert references == expected_references


def test_extract_session_references_edge_cases():
    # Test with various edge cases
    assert extract_thread_references("thread:") == []  # Empty identifier
    assert extract_thread_references("THREAD:123") == []  # Wrong case
    assert extract_thread_references("thread:123!") == ["123"]  # Stops at special char
    assert extract_thread_references("thread:123@test") == ["123"]  # Stops at special char
    assert extract_thread_references("thread:123 thread:456") == ["123", "456"]  # Multiple with space


@pytest.mark.parametrize(
    "original,config,expected,expected_updated",
    [
        ({"key": "${VAR}"}, {"VAR": "value"}, {"key": "value"}, True),  # basic single variable replacement
        (
            {"key": "${VAR1} and ${VAR2}"},
            {"VAR1": "first", "VAR2": "second"},
            {"key": "first and second"},
            True,
        ),  # two variables in single string value
        (
            {"key1": "${VAR1}", "key2": "${VAR2}", "key3": "static"},
            {"VAR1": "value1", "VAR2": "value2"},
            {"key1": "value1", "key2": "value2", "key3": "static"},
            True,
        ),  # multiple dict keys with variables
        (
            {"key": "${VAR} and ${VAR} again"},
            {"VAR": "value"},
            {"key": "value and value again"},
            True,
        ),  # duplicate variable replacements
        (
            {"key1": "value1", "key2": "value2"},
            {"VAR": "value"},
            {"key1": "value1", "key2": "value2"},
            False,
        ),  # static values without variables
        ({}, {"VAR": "value"}, {}, False),  # empty dict remains empty
        ({"key": "${VAR}"}, {}, {}, True),  # unresolved variables remove keys
        ({"key": "static"}, {"VAR": "value"}, {"key": "static"}, False),  # static string unchanged
        ({}, {}, {}, False),  # empty dict and config
        # Variable positions
        ({"key": "${VAR} suffix"}, {"VAR": "X"}, {"key": "X suffix"}, True),  # variable at string start
        ({"key": "prefix ${VAR} suffix"}, {"VAR": "X"}, {"key": "prefix X suffix"}, True),  # variable in string middle
        ({"key": "prefix ${VAR}"}, {"VAR": "X"}, {"key": "prefix X"}, True),  # variable at string end
        (
            {"key": "${VAR1} ${VAR2} ${VAR3}"},
            {"VAR1": "A", "VAR2": "B", "VAR3": "C"},
            {"key": "A B C"},
            True,
        ),  # three spaced variables
        ({"key": "${VAR1}${VAR2}"}, {"VAR1": "A", "VAR2": "B"}, {"key": "AB"}, True),  # adjacent variables no space
        (
            {"key": "text ${VAR1} more ${VAR2} end"},
            {"VAR1": "A", "VAR2": "B"},
            {"key": "text A more B end"},
            True,
        ),  # text interleaved with variables
        (
            {"key": "${VAR1}${VAR2}"},
            {"VAR1": "Hello", "VAR2": "World"},
            {"key": "HelloWorld"},
            True,
        ),  # concatenated adjacent variables
        ({"key": "prefix${VAR}suffix"}, {"VAR": ""}, {"key": "prefixsuffix"}, True),  # empty string replacement
        ({"key": "${VAR}${VAR}${VAR}"}, {"VAR": "X"}, {"key": "XXX"}, True),  # same variable used thrice
        ({"key": "${123}"}, {"123": "num"}, {"key": "num"}, True),  # numeric-only variable name
        # Special variable names
        (
            {"key": "${VAR_WITH_UNDERSCORE}"},
            {"VAR_WITH_UNDERSCORE": "underscore_value"},
            {"key": "underscore_value"},
            True,
        ),  # variable name with underscores
        (
            {"key": "${VAR123}"},
            {"VAR123": "numeric_value"},
            {"key": "numeric_value"},
            True,
        ),  # alphanumeric variable name
        (
            {"key": "${VAR_123_TEST}"},
            {"VAR_123_TEST": "mixed_value"},
            {"key": "mixed_value"},
            True,
        ),  # mixed underscore and numbers
        (
            {"key": "${_PRIVATE_VAR}"},
            {"_PRIVATE_VAR": "private_value"},
            {"key": "private_value"},
            True,
        ),  # leading underscore variable
        (
            {"key": "${VAR1_VAR2_VAR3}"},
            {"VAR1_VAR2_VAR3": "multi_underscore"},
            {"key": "multi_underscore"},
            True,
        ),  # multiple underscores in name
        ({"key": "${A1B2C3}"}, {"A1B2C3": "alphanumeric"}, {"key": "alphanumeric"}, True),  # mixed letters and numbers
        # Invalid patterns - should not match
        ({"key": "${PARTIAL"}, {"PARTIAL": "value"}, {"key": "${PARTIAL"}, False),  # missing closing brace
        ({"key": "PARTIAL}"}, {"PARTIAL": "value"}, {"key": "PARTIAL}"}, False),  # missing opening ${
        ({"key": "${}"}, {"": "value"}, {"key": "${}"}, False),  # empty variable name
        ({"key": "${ VAR }"}, {"VAR": "value"}, {"key": "${ VAR }"}, False),  # spaces inside braces invalid
        ({"key": "${VAR!}"}, {"VAR": "value"}, {"key": "${VAR!}"}, False),  # exclamation mark invalid
        ({"key": "${VAR\n}"}, {"VAR": "value"}, {"key": "${VAR\n}"}, False),  # newline character invalid
        ({"key": "${VAR\t}"}, {"VAR": "value"}, {"key": "${VAR\t}"}, False),  # tab character invalid
        ({"key": "$VAR and $123"}, {"VAR": "value"}, {"key": "$VAR and $123"}, False),  # $ without braces ignored
    ],
)
def test_resolve_config_variables_variable_replacement(original, config, expected, expected_updated):
    """Test various variable replacement scenarios."""
    result, updated = resolve_config_variables(original, config)
    assert result == expected
    assert updated == expected_updated


@pytest.mark.parametrize(
    "original_var,config_var",
    [
        ("${var}", "VAR"),  # lowercase in template, uppercase in config
        ("${VAR}", "var"),  # uppercase in template, lowercase in config
        ("${VaR}", "vAr"),  # mixed case combinations
        ("${VAR_NAME}", "var_name"),  # with underscores
    ],
)
def test_resolve_config_variables_case_insensitive_matching(original_var, config_var):
    """Test that variable matching is case-insensitive."""
    original = {"key": original_var}
    config = {config_var: "value"}
    result, updated = resolve_config_variables(original, config)
    assert result == {"key": "value"}
    assert updated is True


@pytest.mark.parametrize(
    "original,config,expected",
    [
        (
            {"key1": "${VAR1}", "key2": "${UNRESOLVED}"},
            {"VAR1": "value1"},
            {"key1": "value1"},
        ),
        (
            {"key1": "${VAR1}", "key2": "${UNRESOLVED}", "key3": None},
            {"VAR1": "value1"},
            {"key1": "value1", "key3": None},
        ),
        (
            {"key1": "${VAR1}", "key2": "${VAR2} and ${UNRESOLVED}"},
            {"VAR1": "value1", "VAR2": "value2"},
            {"key1": "value1"},
        ),
    ],
)
def test_resolve_config_variables_with_unresolved_variables(original, config, expected):
    """Test handling of unresolved variables in various scenarios."""
    result, updated = resolve_config_variables(original, config)
    assert result == expected
    assert updated is True


def test_resolve_config_variables_with_non_string_values():
    """Test that non-string values pass through unchanged."""
    config = {"VAR": "value"}

    original = {"str": "${VAR}", "int": 42, "bool": True, "none": None, "list": [1, 2, 3]}
    result, updated = resolve_config_variables(original, config)
    assert result == {"str": "value", "int": 42, "bool": True, "none": None, "list": [1, 2, 3]}
    assert updated is True

    original = {"int": 42, "bool": True, "none": None}
    result, updated = resolve_config_variables(original, config)
    assert result == {"int": 42, "bool": True, "none": None}
    assert updated is False


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

    result = replace_all_mentions(text, resolver)
    assert result == expected


def test_replace_all_mentions_with_none_text():
    """Test that None text returns empty string."""

    def resolver(user_id):
        return user_id

    # The function checks for falsy values and returns the input
    assert replace_all_mentions(None, resolver) is None
    assert replace_all_mentions("", resolver) == ""


def test_replace_all_mentions_preserves_whitespace():
    """Test that whitespace is preserved correctly."""

    def resolver(user_id):
        return "resolved"

    assert replace_all_mentions("  @user  ", resolver) == "  resolved  "
    assert replace_all_mentions("\t<@U123>\n", resolver) == "\tresolved\n"
    assert replace_all_mentions("@user1\n\n@user2", resolver) == "resolved\n\nresolved"


def test_replace_all_mentions_with_special_characters():
    """Test mentions with special characters in surrounding text."""
    resolver_mapping = {"user": "john", "U123": "alice"}

    def resolver(user_id):
        return resolver_mapping.get(user_id, user_id)

    assert replace_all_mentions("!@user!", resolver) == "!john!"
    assert replace_all_mentions("#<@U123>$", resolver) == "#alice$"
    assert replace_all_mentions("(@user)", resolver) == "(john)"
    assert replace_all_mentions("[<@U123>]", resolver) == "[alice]"
