from collections import deque
from typing import Generator, Generic, TypeVar

from gensyncio.future import Future
from gensyncio.globs import get_running_loop
from gensyncio.sync import Event

_T = TypeVar("_T")


class Queue(Generic[_T]):
    def __init__(self, maxsize: int = 0) -> None:
        self._maxsize = maxsize
        self._queue: deque[_T] = deque()
        self._getters: deque[Future] = deque()
        self._putters: deque[Future] = deque()
        self._unfinished_tasks = 0
        self._finished = Event()
        self._finished.set()

    def _wakeup_next(self, waiters: deque[Future]) -> None:
        # Wake up the next waiter (if any) that isn't cancelled.
        while waiters:
            waiter = waiters.popleft()
            if not waiter.done():
                waiter.set_result(None)
                break

    def __repr__(self) -> str:
        return f"<{type(self).__name__} at {id(self):#x} {self._format()}>"

    def __str__(self) -> str:
        return f"<{type(self).__name__} {self._format()}>"

    def _format(self) -> str:
        result = f"maxsize={self._maxsize!r}"
        if getattr(self, "_queue", None):
            result += f" _queue={list(self._queue)!r}"
        if self._getters:
            result += f" _getters[{len(self._getters)}]"
        if self._putters:
            result += f" _putters[{len(self._putters)}]"
        if self._unfinished_tasks:
            result += f" tasks={self._unfinished_tasks}"
        return result

    def qsize(self) -> int:
        return len(self._queue)

    @property
    def maxsize(self) -> int:
        return self._maxsize

    def empty(self) -> bool:
        return not self._queue

    def full(self) -> bool:
        if self._maxsize <= 0:
            return False
        return len(self._queue) >= self._maxsize

    def put_nowait(self, item: _T) -> None:
        if self.full():
            raise ValueError("Queue is full")
        self._queue.append(item)
        self._unfinished_tasks += 1
        self._finished.clear()
        self._wakeup_next(self._getters)

    def get_nowait(self) -> _T:
        if not self._queue:
            raise ValueError("Queue is empty")
        item = self._queue.popleft()
        self._wakeup_next(self._putters)
        return item

    def put(self, item: _T) -> Generator[None, None, None]:
        while self.full():
            putter = get_running_loop().create_future()
            self._putters.append(putter)
            try:
                yield from putter
            except Exception:
                putter.set_result(None)
                try:
                    # Clean self._putters from canceled putters.
                    self._putters.remove(putter)
                except ValueError:
                    # The putter could be removed from self._putters by a
                    # previous get_nowait call.
                    pass
                if not self.full() and self._putters:
                    # If the queue is not full and there are no more putters
                    # then we can break the loop.
                    self._wakeup_next(self._putters)
                raise
        return self.put_nowait(item)

    def get(self) -> Generator[None, None, _T]:
        while self.empty():
            getter = get_running_loop().create_future()
            self._getters.append(getter)
            try:
                yield from getter
            except:
                getter.set_result(None)  # Just in case getter is not done yet.
                try:
                    # Clean self._getters from canceled getters.
                    self._getters.remove(getter)
                except ValueError:
                    # The getter could be removed from self._getters by a
                    # previous put_nowait call.
                    pass
                if not self.empty() and self._getters:
                    # We were woken up by put_nowait(), but can't take
                    # the call.  Wake up the next in line.
                    self._wakeup_next(self._getters)
                raise
        return self.get_nowait()

    def task_done(self) -> None:
        if self._unfinished_tasks <= 0:
            raise ValueError("task_done() called too many times")
        self._unfinished_tasks -= 1
        if self._unfinished_tasks == 0:
            self._finished.set()

    def join(self) -> Generator[None, None, None]:
        if self._unfinished_tasks > 0:
            yield from self._finished.wait()
