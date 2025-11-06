from asyncio import CancelledError, Queue, Task, create_task, sleep
from typing import Awaitable, Callable, Generic, TypeVar

T = TypeVar("T")


class BurstBuffer(Generic[T]):
    def __init__(self, callback: Callable[[list[T]], Awaitable[None]], min_interval: float = 2) -> None:
        self.callback = callback
        self.min_interval = min_interval
        self._queue: Queue[T] = Queue()
        self._task: Task = create_task(self._work())

    def cancel(self) -> None:
        self._task.cancel()

    def update(self, elem: T) -> None:
        self._queue.put_nowait(elem)

    async def _drain(self) -> list[T]:
        elems = []
        while not self._queue.empty():
            item = self._queue.get_nowait()
            elems.append(item)
        return elems

    async def _work(self):
        while True:
            try:
                elem = await self._queue.get()
            except CancelledError:
                break
            else:
                elems = await self._drain()
                elems.insert(0, elem)
                await self.callback(elems)
                await sleep(self.min_interval)
