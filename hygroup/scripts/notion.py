import argparse
import asyncio
from pathlib import Path

from aioconsole import ainput

from hygroup.connect.notion import NotionAuth


async def main(args):
    if args.username is None:
        username = await ainput("Username: ")
    else:
        username = args.username

    auth = NotionAuth(root_path=args.token_store)

    if args.command == "authorize":
        await auth.authorize(username)
    elif args.command == "refresh":
        await auth.refresh(username)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        choices=["authorize", "refresh"],
    )
    parser.add_argument(
        "--username",
        type=str,
    )
    parser.add_argument(
        "--token-store",
        type=Path,
        default=Path(".data", "users"),
    )

    asyncio.run(main(parser.parse_args()))
