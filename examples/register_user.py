import asyncio
import os
from getpass import getpass

from dotenv import load_dotenv

from hygroup.user import User
from hygroup.user.default import DefaultUserRegistry
from hygroup.utils import arun


async def main():
    username = await arun(input, "Enter username: ")
    password = await arun(getpass, "Enter password: ")

    print("Enter environment variable names (one per line, empty line to finish):")
    secrets = {}
    while True:
        env_var = await arun(input, "Environment variable name: ")
        env_var = env_var.strip()
        if not env_var:
            break
        secrets[env_var] = os.environ[env_var]

    print("Enter gateway usernames (one per line, empty line to skip):")
    mappings = {}
    for gateway in ["slack", "github"]:
        gateway_username = await arun(input, f"Enter {gateway} username: ")
        gateway_username = gateway_username.strip()
        if gateway_username:
            mappings[gateway] = gateway_username

    user = User(name=username, secrets=secrets, mappings=mappings)
    await DefaultUserRegistry().register(user, password)


if __name__ == "__main__":
    load_dotenv()
    asyncio.run(main())
