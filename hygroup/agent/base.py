from asyncio import Future
from dataclasses import dataclass
from typing import Any


@dataclass
class PermissionRequest:
    tool_name: str
    tool_args: tuple
    tool_kwargs: dict[str, Any]
    ftr: Future

    @property
    def call(self) -> str:
        args_str = ", ".join([repr(arg) for arg in self.tool_args])
        kwargs_str = ", ".join([f"{k}={repr(v)}" for k, v in self.tool_kwargs.items()])
        all_args = ", ".join(filter(None, [args_str, kwargs_str]))
        return f"{self.tool_name}({all_args})"

    async def response(self) -> int:
        return await self.ftr

    def respond(self, granted: int | bool):
        self.ftr.set_result(granted)

    def deny(self):
        self.respond(0)

    def grant_once(self):
        self.respond(1)

    def grant_session(self):
        self.respond(2)

    def grant_always(self):
        self.respond(3)


@dataclass
class FeedbackRequest:
    question: str
    ftr: Future

    async def response(self) -> str:
        return await self.ftr

    def respond(self, text: str):
        self.ftr.set_result(text)
