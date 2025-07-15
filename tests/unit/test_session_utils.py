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
    references = Session.extract_thread_references(text)
    assert references == expected_references


def test_extract_session_references_edge_cases():
    # Test with various edge cases
    assert Session.extract_thread_references("thread:") == []  # Empty identifier
    assert Session.extract_thread_references("THREAD:123") == []  # Wrong case
    assert Session.extract_thread_references("thread:123!") == ["123"]  # Stops at special char
    assert Session.extract_thread_references("thread:123@test") == ["123"]  # Stops at special char
    assert Session.extract_thread_references("thread:123 thread:456") == ["123", "456"]  # Multiple with space
