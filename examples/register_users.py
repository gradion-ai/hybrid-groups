import asyncio
from getpass import getpass

from hygroup.user import User
from hygroup.user.default import DefaultUserRegistry
from hygroup.utils import arun


async def main():
    registry = DefaultUserRegistry()
    await registry.unlock("admin")

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
    asyncio.run(main())
