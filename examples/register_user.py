import asyncio
import os

from dotenv import load_dotenv

from hygroup.user import User
from hygroup.user.default import DefaultUserRegistry
from hygroup.utils import arun


async def main():
    registry = DefaultUserRegistry()
    await registry.unlock("admin")

    if user := registry.get_user("martin"):
        print("User martin already registered")
        return

    secrets = {
        "FIRECRAWL_API_KEY": os.environ["FIRECRAWL_API_KEY"],
        "BRAVE_API_KEY": os.environ["BRAVE_API_KEY"],
    }

    for username in ["martin", "chris", "erich", "chief"]:
        await arun(print, f"Enter gateway usernames for user {username} (one per line, empty line to skip):")

        mappings = {}
        for gateway in ["slack", "github"]:
            gateway_username = await arun(input, f"Enter {gateway} username: ")
            gateway_username = gateway_username.strip()
            if gateway_username:
                mappings[gateway] = gateway_username

        user = User(name=username, secrets=secrets, mappings=mappings)
        await registry.register(user, password=username)


if __name__ == "__main__":
    load_dotenv()
    asyncio.run(main())
