import argparse
import asyncio
from getpass import getpass
from pathlib import Path

from hygroup.user import User
from hygroup.user.default import DefaultUserRegistry
from hygroup.utils import arun


async def main(args):
    registry = DefaultUserRegistry(args.user_registry)
    await registry.unlock(args.user_registry_password)

    username = await arun(input, "Enter username: ")
    password = await arun(getpass, "Enter password (Enter for none): ")

    print("Enter secrets in format KEY=VALUE (one per line, empty line to finish):")
    secrets = {}
    while True:
        secret = await arun(input, "Secret: ")
        if not secret.strip():
            break
        key, value = secret.split("=", 1)
        secrets[key.strip()] = value.strip()

    print("Enter gateway usernames (one per line, empty line to skip):")
    mappings = {}
    for gateway in ["slack", "github"]:
        gateway_username = await arun(input, f"Enter {gateway} username: ")
        gateway_username = gateway_username.strip()
        if gateway_username:
            mappings[gateway] = gateway_username

    user = User(name=username, secrets=secrets, mappings=mappings)
    await registry.register(user, password=password or None)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Hybrid Groups user registration")
    parser.add_argument(
        "--user-registry",
        type=Path,
        default=Path(".data", "users", "registry.bin"),
        help="Path to the user registry file.",
    )
    parser.add_argument(
        "--user-registry-password",
        type=str,
        default="admin",
        help="Admin password for creating or unlocking the user registry.",
    )

    args = parser.parse_args()
    asyncio.run(main(args=args))
