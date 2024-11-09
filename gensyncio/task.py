from typing import TYPE_CHECKING, Generator, Any, Callable
import uuid

from gensyncio.exceptions import GenCancelledError

if TYPE_CHECKING:
    from gensyncio.loop import Loop


class Task[_G, _R]:
    def __init__(self, gen: Generator[Any, _G, _R]) -> None:
        self.gen = gen
        self.id = uuid.uuid4()
        self.status = "pending"
        self.loop: "Loop | None" = None
        self.callbacks: list[Callable[[Task[_G, _R]], None]] = []
        self.result: _R | None = None

    def __iter__(self) -> "Task[_G, _R]":
        return self

    def __next__(self) -> _G:
        return next(self.gen)

    def throw(self, exc: BaseException) -> _G:
        return self.gen.throw(exc)

    def set_result(self, result: _R) -> None:
        self.result = result

    def set_done(self) -> None:
        if self.status == "cancelled":
            return
        self.status = "finished"

    def done(self) -> bool:
        if self.status == "cancelled":
            return True
        return self.status == "finished"

    def cacnel(self) -> None:
        self.status = "cancelled"
        self.gen.throw(GenCancelledError())

    def add_done_callback(self, callback: "Callable[[Task[_G, _R]], None]") -> None:
        self.callbacks.append(callback)

    def set_loop(self, loop: "Loop") -> None:
        self.loop = loop

    def __hash__(self) -> int:
        return hash(self.id)

    def __eq__(self, value: object, /) -> bool:
        if not isinstance(value, Task):
            return False
        return self.id == value.id
