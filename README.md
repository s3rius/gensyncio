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
