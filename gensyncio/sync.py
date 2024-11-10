"""Syncranisation primitives for async code."""

from collections import deque
from typing import Any, Generator

from gensyncio.exceptions import GenCancelledError
from gensyncio.future import Future
from gensyncio.globs import get_running_loop


class Lock:
    def __init__(self) -> None:
        self._waiters: deque[Future] = deque()
        self._locked = False

    def acquire(self) -> Generator[None, None, bool]:
        if not self._locked and not self._waiters:
            self._locked = True
            return True

        fut = get_running_loop().create_future()
        self._waiters.append(fut)
        try:
            try:
                yield from fut
            finally:
                self._waiters.remove(fut)
        except GenCancelledError:
            if not self._locked:
                self._wake_up_next()
            raise

        self._locked = True
        return True

    def release(self) -> None:
        if not self._locked:
            raise RuntimeError("Lock is not acquired.")
        self._locked = False
        self._wake_up_next()

    def locked(self) -> bool:
        return self._locked

    def _wake_up_next(self) -> None:
        if not self._waiters:
            return
        try:
            fut = next(iter(self._waiters))
        except StopIteration:
            return

        if not fut.done():
            fut.set_result(True)

    def __repr__(self) -> str:
        res = super().__repr__()
        extra = "locked" if self._locked else "unlocked"
        if self._waiters:
            extra = f"{extra}, waiters:{len(self._waiters)}"
        return f"<{res[1:-1]} [{extra}]>"

    def __enter__(self) -> Generator[None, None, "Lock"]:
        yield from self.acquire()
        return self

    def __exit__(self, *_args: Any) -> None:
        self.release()


class Event:
    def __init__(self) -> None:
        self._waiters: deque[Future] = deque()
        self._value = False

    def is_set(self) -> bool:
        return self._value

    def set(self) -> None:
        if self._value:
            return
        self._value = True
        for fut in self._waiters:
            if not fut.done():
                fut.set_result(True)

    def clear(self) -> None:
        self._value = False

    def wait(self) -> Generator[None, None, bool]:
        if self._value:
            return True

        fut = get_running_loop().create_future()
        self._waiters.append(fut)
        try:
            yield from fut
            return True
        finally:
            self._waiters.remove(fut)

    def __repr__(self) -> str:
        res = super().__repr__()
        extra = "set" if self._value else "unset"
        if self._waiters:
            extra = f"{extra}, waiters:{len(self._waiters)}"
        return f"<{res[1:-1]} [{extra}]>"
