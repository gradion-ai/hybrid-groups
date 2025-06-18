import re
from typing import Any

CONFIG_VARIABLE_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)\}", re.IGNORECASE)


def resolve_config_variables(
    original_data: dict[str, Any],
    config_values: dict[str, str],
) -> tuple[dict[str, Any | None], bool]:
    """Replaces ${VARIABLE_NAME} patterns in a dictionary using case-insensitive lookup.
    Unresolved variables are removed from the output dictionary.
    Returns a tuple of (modified_dict, was_updated) where was_updated indicates if any changes were made.
    """
    if not original_data:
        return {}, False

    normalized_config_values = {k.upper(): v for k, v in config_values.items()}
    has_changes = False
    new_data = {}

    for key, value in original_data.items():
        if value is None or not isinstance(value, str):
            new_data[key] = value
        else:
            matches = CONFIG_VARIABLE_PATTERN.findall(value)
            if matches:
                result = value
                all_resolved = True
                for var_name in matches:
                    lookup_key = var_name.upper()
                    if lookup_key not in normalized_config_values:
                        all_resolved = False
                        break
                    else:
                        result = result.replace(f"${{{var_name}}}", normalized_config_values[lookup_key])  # type: ignore
                if all_resolved:
                    new_data[key] = result
                has_changes = True
            else:
                new_data[key] = value

    return new_data, has_changes
