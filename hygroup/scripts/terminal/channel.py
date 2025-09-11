import argparse
import asyncio

from hygroup.channel import RequestClient
from hygroup.utils import arun


async def main(args):
    client = RequestClient()

    if args.username is None:
        username = await arun(input, "Enter username: ")
    else:
        username = args.username

    if await client.connect(username=username):
        await client.join()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", type=str, default=None)
    asyncio.run(main(args=parser.parse_args()))
