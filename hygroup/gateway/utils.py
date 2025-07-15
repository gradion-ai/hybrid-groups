import re
from typing import Callable


def extract_initial_mention(text):
    if not text:
        return None, text

    # Match '@name' or '<@name>' at the beginning, with optional surrounding whitespace.
    match = re.match(r"^\s*(?:<@([/\w-]+)>|@([/\w-]+))\s*([\s\S]*)", text)

    if match:
        name = match.group(1) or match.group(2)
        remaining_text = match.group(3)
        return name, remaining_text

    return None, text


def resolve_mentions(text: str | None, resolver: Callable[[str], str]) -> str | None:
    """Replace all mentions with resolved usernames.

    Finds all mentions in both formats (@username and <@userid>) and replaces
    them with the resolved username (without @).

    Args:
        text: The text containing the mentions to replace
        resolver: Function that takes a username and returns the resolved username

    Returns:
        Text with all mentions replaced by resolved usernames
    """
    if not text:
        return text

    # Replace <@userid> format mentions
    def resolve_bracket_mention(match):
        user_id = match.group(1)
        resolved = resolver(user_id)
        # If resolver returns the same ID (unknown user), use it without brackets
        return resolved

    # Replace @username format mentions
    def resolve_at_mention(match):
        username = match.group(1)
        resolved = resolver(username)
        # Remove @ from the resolved name
        return resolved

    # First replace <@userid> format
    text = re.sub(r"<@([/\w-]+)>", resolve_bracket_mention, text)

    # Then replace @username format
    text = re.sub(r"@([/\w-]+)", resolve_at_mention, text)

    return text
