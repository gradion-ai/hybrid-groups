import argparse
import asyncio
from getpass import getpass

from hygroup.gateway.terminal import TerminalClient
from hygroup.utils import arun


async def main(args):
    client = TerminalClient()

    if args.username is None:
        username = await arun(input, "Enter username: ")
    else:
        username = args.username

    if args.password is None:
        password = await arun(getpass, "Enter password: ")
    else:
        password = args.password

    if await client.authenticate(username, password):
        await client.join()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", type=str, default=None)
    parser.add_argument("--password", type=str, default=None)
    asyncio.run(main(args=parser.parse_args()))
