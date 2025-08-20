import pytest

from hygroup.session import Session


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
    references = Session._extract_thread_references(text)
    assert references == expected_references


def test_extract_session_references_edge_cases():
    # Test with various edge cases
    assert Session._extract_thread_references("thread:") == []  # Empty identifier
    assert Session._extract_thread_references("THREAD:123") == []  # Wrong case
    assert Session._extract_thread_references("thread:123!") == ["123"]  # Stops at special char
    assert Session._extract_thread_references("thread:123@test") == ["123"]  # Stops at special char
    assert Session._extract_thread_references("thread:123 thread:456") == ["123", "456"]  # Multiple with space


@pytest.mark.parametrize(
    "text, expected_name, expected_remaining",
    [
        ("@user1 hello world", "user1", "hello world"),
        ("  @user-3  baz", "user-3", "baz"),
        (" @user-4   qux", "user-4", "qux"),
        ("@user5", "user5", ""),
        ("no mention here", None, "no mention here"),
        ("", None, ""),
        ("   ", None, "   "),
        ("  @user7", "user7", ""),
        ("  @user-9text", "user-9text", ""),  # All word characters are part of username
        ("@user10text", "user10text", ""),  # No space required after username
        ("@user/sub hello", "user/sub", "hello"),  # Slash in username
        ("@bot-name", "bot-name", ""),  # Hyphen in username
    ],
)
def test_extract_initial_mention(text, expected_name, expected_remaining):
    """Test Session._extract_initial_mention static method."""
    name, remaining = Session._extract_initial_mention(text)
    assert name == expected_name
    assert remaining == expected_remaining


def test_extract_initial_mention_no_match_for_email_like_strings():
    """Test that email addresses are not matched as mentions."""
    text = "user@example.com some text"
    name, remaining = Session._extract_initial_mention(text)
    assert name is None
    assert remaining == text


def test_extract_initial_mention_with_special_chars_in_remaining_text():
    """Test extraction with special characters in the remaining text."""
    text = "@user1 !@#$%^&*()_+"
    name, remaining = Session._extract_initial_mention(text)
    assert name == "user1"
    assert remaining == "!@#$%^&*()_+"

    text = "@user2  !@#$%^&*()_+"
    name, remaining = Session._extract_initial_mention(text)
    assert name == "user2"
    assert remaining == "!@#$%^&*()_+"


def test_extract_initial_mention_edge_cases():
    """Test edge cases for initial mention extraction."""
    # Multiple @ symbols - doesn't match because @@ is not a valid mention start
    name, remaining = Session._extract_initial_mention("@@user")
    assert name is None  # @@ doesn't match the pattern @word
    assert remaining == "@@user"

    # @ alone at the beginning
    name, remaining = Session._extract_initial_mention("@ hello")
    assert name is None  # @ followed by space doesn't match the pattern
    assert remaining == "@ hello"

    # Whitespace variations
    name, remaining = Session._extract_initial_mention("\t@user\n")
    assert name == "user"
    assert remaining == ""  # The trailing \n is consumed by \s* after username

    name, remaining = Session._extract_initial_mention("  @user  \n  more text")
    assert name == "user"
    assert remaining == "more text"  # Whitespace after username is consumed
