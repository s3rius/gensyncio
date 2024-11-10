# Generator-based async framework

This project was created for educational purpose to demonstrate people how to write their own async
framework with event loop, socket primitives and an HTTP server.


# Lib

The lib is pretty similar with asyncio module. Here's a simple example of an async program:


```python
from typing import Generator
import gensyncio


def main() -> Generator[None, None, None]:
    yield from gensyncio.sleep(1)
    print("Hello from async!")


print(gensyncio.run(main()))
```

You can achieve real async by creating tasks in an event loop and gathering them.

```python
from typing import Generator
import gensyncio


def print_after_delay(msg: str, delay: int):
    yield from gensyncio.sleep(delay)
    print(msg)


def main() -> Generator[None, None, None]:
    yield from gensyncio.gather(
        print_after_delay("Hello", 1),
        print_after_delay("from", 1),
        print_after_delay("async", 1),
    )


gensyncio.run(main())
```

# Sync primitives

This lib implements syncronization primitives for async programming. Such as:

* Event
* Lock

Here are examples of how they should be used:

An event:
```python
import gensyncio


def waiter(event: gensyncio.Event):
    print("waiting for it ...")
    yield from event.wait()
    print("... got it!")


def main():
    # Create an Event object.
    event = gensyncio.Event()

    # Spawn a Task to wait until 'event' is set.
    waiter_task = gensyncio.create_task(waiter(event))

    # Sleep for 1 second and set the event.
    yield from gensyncio.sleep(1)
    event.set()

    # Wait until the waiter task is finished.
    yield from waiter_task


gensyncio.run(main())
```

A lock:

```python
from typing import Generator
import gensyncio


def print_after(lock: gensyncio.Lock, delay: float, val: str) -> Generator[None, None, None]:
    """Print after delay, but wit aquiring a lock."""
    # Here we are using the lock as a context manager
    with lock as _lock:
        # This will yield from the lock, and wait until the lock is released
        yield from _lock
        # This will yield from the sleep, and wait until the sleep is done
        yield from gensyncio.sleep(delay)
    print(val)


def main() -> Generator[None, None, None]:
    loop = gensyncio.get_running_loop()
    lock = gensyncio.Lock()
    loop.create_task(print_after(lock, 2, "one"))
    t = loop.create_task(print_after(lock, 1, "two"))
    # Here we wait for the task to finish
    yield from t


gensyncio.run(main())
```

# Queue

The queue is the same as asyncio Queue. This example is rewritten asyncio.Queue example from python docs.

```python
import random
import time

import gensyncio


def worker(name: str, queue: gensyncio.Queue[float]):
    while True:
        # Get a "work item" out of the queue.
        sleep_for = yield from queue.get()

        # Sleep for the "sleep_for" seconds.
        yield from gensyncio.sleep(sleep_for)

        # Notify the queue that the "work item" has been processed.
        queue.task_done()

        print(f"{name} has slept for {sleep_for:.2f} seconds")


def main():
    # Create a queue that we will use to store our "workload".
    queue = gensyncio.Queue()

    # Generate random timings and put them into the queue.
    total_sleep_time = 0
    for _ in range(20):
        sleep_for = random.uniform(0.05, 1.0)
        total_sleep_time += sleep_for
        queue.put_nowait(sleep_for)

    # Create three worker tasks to process the queue concurrently.
    tasks = []
    for i in range(3):
        task = gensyncio.create_task(worker(f"worker-{i}", queue))
        tasks.append(task)

    # Wait until the queue is fully processed.
    started_at = time.monotonic()
    yield from queue.join()
    total_slept_for = time.monotonic() - started_at

    # Cancel our worker tasks.
    for task in tasks:
        try:
            task.cancel()
        except gensyncio.GenCancelledError:
            pass
    # Wait until all worker tasks are cancelled.
    yield from gensyncio.gather(*tasks)

    print("====")
    print(f"3 workers slept in parallel for {total_slept_for:.2f} seconds")
    print(f"total expected sleep time: {total_sleep_time:.2f} seconds")


gensyncio.run(main())
```

# Sockets

Also this lib contains a simple socket implementation which is compatible with generators approach.
Here's a simple example of using generator based socket:

```python
import socket
from typing import Generator
import gensyncio
from gensyncio.gensocket import GenSocket


def main() -> Generator[None, None, None]:
    sock = GenSocket(socket.AF_INET, socket.SOCK_STREAM)
    yield from sock.connect(("httpbin.org", 80))
    sock.send(b"GET /get HTTP/1.1\r\nHost: httpbin.org\r\n\r\n")
    resp = yield from sock.recv(1024)
    print(resp.decode("utf-8"))


gensyncio.run(main())
```

GenSocket is alsmost similar to [socket.socket](https://docs.python.org/3/library/socket.html) except it's always nonblocking and some of it's methods should be awaited using `yield from`.


# Http module

Also there's a small HTTP module which you can use to serve and send requests. 

Here's a client usage example:

```python
import gensyncio
from gensyncio.http import ClientRequest


def main():
    yield
    req = ClientRequest("http://localhost:8080/", "GET", json={"one": "two"})
    resp = yield from req.send()
    print(resp)
    print(resp.body.decode("utf-8"))


gensyncio.run(main())
```

And here's a simple echo server example:

```python
import logging
from typing import Generator
from gensyncio.http import Server
import gensyncio
from gensyncio.http.server import Request, Response

app = Server()


@app.router.get("/")
def index(req: Request) -> Generator[None, None, Response]:
    body = yield from req.read()
    return Response(status=200, body=body, content_type=req.content_type)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    gensyncio.run(app.run(host="0.0.0.0", port=8080))
```
