from typing import Any, Generator, TypeVar
from gensyncio.exceptions import GenCancelledError
from gensyncio.globs import set_running_loop
from gensyncio.task import Task
import copy


_R = TypeVar("_R")


class Loop:
    def __init__(self) -> None:
        self.running: list[Task[Any, Any]] = []
        self.to_delete: list[Task[Any, Any]] = []
        self.to_add: list[Task[Any, Any]] = []

    def tick(self):
        for task in self.to_add:
            task.set_loop(self)
            self.running.append(task)
        self.to_add.clear()

        for task in self.running:
            try:
                next(task)
            except StopIteration as e:
                task.set_result(e.value)
                task.set_done()
                self.to_delete.append(task)

        for task in self.to_delete:
            for cb in task.callbacks:
                cb(task)
            try:
                self.running.remove(task)
            except ValueError:
                continue
        done = copy.copy(self.to_delete)
        self.to_delete.clear()
        return done

    def create_task(
        self, task: Generator[Any, Any, _R] | Task[Any, _R]
    ) -> Task[Any, _R]:
        if isinstance(task, Generator):
            task_gen = Task(task)
        else:
            task_gen = task
        task_gen.set_loop(self)
        self.add_task(task_gen)
        return task_gen

    def add_task(self, task: Task):
        self.to_add.append(task)

    def run_forever(self):
        set_running_loop(self)
        while True:
            self.tick()

    def cancel_all(self):
        for task in self.running:
            try:
                task.cancel()
            except GenCancelledError:
                continue
        # We do one more tick to advance all generators to the end.
        self.tick()

    def run_until_complete(
        self, task: Generator[Any, Any, _R] | Task[Any, _R]
    ) -> _R | None:
        set_running_loop(self)
        task = self.create_task(task)
        while True:
            if task.done():
                self.cancel_all()
                return task.result
            self.tick()
