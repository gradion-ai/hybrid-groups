import json

from hygroup.gateway.slack_config.models import ValidationError


class AgentValidator:
    @staticmethod
    def validate_name(name: str, existing_names: list[str] | None = None) -> ValidationError | None:
        if not name or not name.strip():
            return ValidationError(field="agent_name", message="Agent name is required")

        if existing_names and name.strip() in existing_names:
            return ValidationError(field="agent_name", message="Agent name must be unique")

        return None

    @staticmethod
    def validate_description(description: str) -> ValidationError | None:
        if not description or not description.strip():
            return ValidationError(field="agent_description", message="Description is required")
        return None

    @staticmethod
    def validate_model(model_str: str) -> tuple[dict | str | None, ValidationError | None]:
        if not model_str or not model_str.strip():
            return None, ValidationError(field="agent_model", message="Model is required")

        model_str = model_str.strip()

        # Try to parse as JSON first
        try:
            model_data = json.loads(model_str)
            return model_data, None
        except json.JSONDecodeError:
            # If JSON parsing fails, treat as string (which is valid)
            # Check if it looks like an attempted JSON object that failed parsing
            if model_str.startswith("{") and model_str.endswith("}"):
                return None, ValidationError(
                    field="agent_model", message="Invalid JSON format. For JSON objects, ensure proper syntax."
                )
            elif model_str.startswith("[") and model_str.endswith("]"):
                return None, ValidationError(
                    field="agent_model", message="Model cannot be a JSON array. Use a string or JSON object."
                )
            else:
                # Valid string format
                return model_str, None

    @staticmethod
    def validate_instructions(instructions: str) -> ValidationError | None:
        if not instructions or not instructions.strip():
            return ValidationError(field="agent_instructions", message="Instructions are required")
        return None

    @staticmethod
    def validate_mcp_settings(mcp_str: str) -> tuple[list | None, ValidationError | None]:
        if not mcp_str or not mcp_str.strip():
            return [], None  # Empty is valid, return empty list

        mcp_str = mcp_str.strip()

        try:
            mcp_data = json.loads(mcp_str)
            # Ensure it's a list
            if not isinstance(mcp_data, list):
                return None, ValidationError(
                    field="agent_mcp_settings", message="MCP settings must be a JSON array (list)."
                )
            return mcp_data, None
        except json.JSONDecodeError as e:
            return None, ValidationError(field="agent_mcp_settings", message=f"Invalid JSON: {str(e)}")

    @staticmethod
    def validate_agent_data(
        name: str,
        description: str,
        model_str: str,
        instructions: str,
        mcp_settings_str: str = "",
        existing_names: list[str] | None = None,
        validate_name_field: bool = True,
    ) -> dict[str, str]:
        errors = {}

        # Validate name
        if validate_name_field:
            if error := AgentValidator.validate_name(name, existing_names):
                errors[error.field] = error.message

        # Validate description
        if error := AgentValidator.validate_description(description):
            errors[error.field] = error.message

        # Validate model
        _, error = AgentValidator.validate_model(model_str)
        if error:
            errors[error.field] = error.message

        # Validate instructions
        if error := AgentValidator.validate_instructions(instructions):
            errors[error.field] = error.message

        # Validate MCP settings
        _, error = AgentValidator.validate_mcp_settings(mcp_settings_str)
        if error:
            errors[error.field] = error.message

        return errors
