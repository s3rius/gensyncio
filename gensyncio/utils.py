import time
from typing import Any, Generator, Tuple
from uuid import UUID

from gensyncio.loop import Loop
from gensyncio.task import Task
from .globs import get_running_loop


def sleep(delay: float) -> Generator[None, None, None]:
    start = time.time()
    while time.time() - start < delay:
        yield


def gather(
    *futures: Generator[Any, Any, Any] | Task[Any, Any],
    timeout: float | None = None,
) -> Generator[None, None, Tuple[Any, ...]]:
    loop = get_running_loop()
    start_time = time.time()
    tasks = [loop.create_task(future) for future in futures]
    ordered_ids = [task.id for task in tasks]
    results: dict[UUID, Any] = {}
    while tasks:
        for task in tasks:
            if task.done():
                results[task.id] = task.result
                tasks.remove(task)
        if timeout and time.time() - start_time > timeout:
            raise TimeoutError(f"Timeout on tasks: {ordered_ids}")
        yield
    return tuple(results[id] for id in ordered_ids)


def run(coro: Generator[Any, Any, Any] | Task[Any, Any]) -> Any:
    try:
        loop = get_running_loop()
    except RuntimeError:
        loop = Loop()
    return loop.run_until_complete(coro)
