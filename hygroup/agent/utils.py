import importlib

from pydantic_ai.models import Model


def model_from_dict(model_dict: dict) -> Model:
    # Extract model configuration
    model_args = model_dict["args"].copy()

    # Check if provider configuration exists
    if "provider" in model_args:
        provider_config = model_args["provider"]
        provider_class_name = provider_config["class"]
        provider_args = provider_config["args"]

        # Import and instantiate provider
        module_name, class_name = provider_class_name.rsplit(".", 1)
        provider_module = importlib.import_module(module_name)
        provider_class = getattr(provider_module, class_name)
        provider = provider_class(**provider_args)

        # Replace provider config with instantiated provider
        model_args["provider"] = provider

    # Import and instantiate model
    model_class_name = model_dict["class"]
    module_name, class_name = model_class_name.rsplit(".", 1)
    model_module = importlib.import_module(module_name)
    model_class = getattr(model_module, class_name)
    model = model_class(**model_args)

    return model
