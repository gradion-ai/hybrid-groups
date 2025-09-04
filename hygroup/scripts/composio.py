import argparse
import asyncio
from pathlib import Path

from dotenv import load_dotenv

from hygroup.connect.composio import ComposioConnector
from hygroup.user.default.registry import DefaultUserRegistry


async def main(args):
    connector = ComposioConnector(
        user_registry=DefaultUserRegistry(),
        config_path=args.connector_config_path,
        toolkits_path=args.toolkit_config_path,
    )

    if args.command == "setup":
        await connector.setup()
    elif args.command == "cleanup":
        await connector.cleanup()
    elif args.command == "tools":
        if not args.toolkit:
            print("Error: toolkit argument is required for 'tools' command")
            exit(1)
        tools = await connector.tools(args.toolkit)
        for tool_key, description in tools.items():
            print(tool_key)
            print(description)
            print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Composio connector setup and cleanup")

    parser.add_argument(
        "command",
        choices=["setup", "cleanup", "tools"],
        help="Command to execute: setup, cleanup, or tools",
    )
    parser.add_argument(
        "toolkit",
        nargs="?",
        help="Toolkit name (required for 'tools' command)",
    )
    parser.add_argument(
        "--connector-config-path",
        type=Path,
        default=Path(".data", "composio", "config.json"),
        help="Path to the Composio connector configuration file.",
    )
    parser.add_argument(
        "--toolkit-config-path",
        type=Path,
        default=None,
        help="Path to the toolkit configuration file (default: uses built-in toolkits.json).",
    )

    load_dotenv()
    asyncio.run(main(parser.parse_args()))
