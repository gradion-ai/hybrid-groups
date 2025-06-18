import asyncio
from functools import partial
from typing import Callable, TypeVar

T = TypeVar("T")


async def arun(func: Callable[..., T], *args, **kwargs) -> T:
    return await asyncio.get_running_loop().run_in_executor(None, partial(func, *args, **kwargs))
