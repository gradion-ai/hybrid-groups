import pytest

from hygroup.agent.default.utils import resolve_config_variables


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
