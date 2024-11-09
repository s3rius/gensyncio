import json
from typing import Generator, Callable, Any, Tuple

import socket
from gensyncio.gensocket import GenSocket
from gensyncio.globs import get_running_loop
from gensyncio.http.parser import parse_http_message
import logging

logger = logging.getLogger(__name__)


class RouteNotFound(Exception):
    def __init__(self, path: str):
        self.path = path
        super().__init__(f"Route not found: {path}")


class Request:
    def __init__(
        self,
        http_version: str,
        path: str,
        method: str,
        headers: dict[str, bytes],
        read_body: bytearray,
        body_reader: GenSocket,
        peer_addr: Tuple[str, int],
    ) -> None:
        self.http_version = http_version
        self.path = path
        self.method = method
        self.headers = headers
        self._read_body = read_body
        self._full_body = None
        self._body_reader = body_reader
        self.peer_addr = peer_addr
        self.content_length = int(headers.get("content-length", b"0"))
        self.content_type = headers.get("content-type", b"text/plain").decode("utf-8")

    def __repr__(self) -> str:
        return f"<Request {self.method} {self.path} {self.peer_addr}>"

    def read(self) -> Generator[None, None, bytes]:
        if not self._full_body:
            while len(self._read_body) < self.content_length:
                data = yield from self._body_reader.recv(1024)
                self._read_body.extend(data)
            self._full_body = bytes(self._read_body)

        return self._full_body

    def json(self) -> Generator[None, None, Any]:
        body = yield from self.read()
        return json.loads(body)


class Response:
    def __init__(
        self,
        status: int = 200,
        reason: str = "OK",
        body: bytes | None = None,
        text: str | None = None,
        content_type: str = "text/plain",
        headers: dict[str, str] | None = None,
    ) -> None:
        if body is not None and text is not None:
            raise ValueError("body and text are not allowed together")
        self.status = status
        self.reason = reason
        self.body = b""
        if body:
            self.body = body
        elif text:
            self.body = text.encode("utf-8")
        self.content_type = content_type
        self.headers = headers or {}
        self.http_version = "HTTP/1.1"

    def set_http_version(self, version: str) -> None:
        self.http_version = version

    def __bytes__(self) -> bytes:
        headers = {
            **self.headers,
            "Content-Length": str(len(self.body)),
            "Content-Type": self.content_type,
        }
        status_line = f"{self.http_version} {self.status} {self.reason}"
        headers_str = "\r\n".join(f"{k}: {v}" for k, v in headers.items())
        response = bytearray(f"{status_line}\r\n{headers_str}\r\n\r\n".encode("utf-8"))
        response.extend(self.body)
        return bytes(response)

    def __repr__(self) -> str:
        return f"<Response {self.status} {self.content_type}>"


HandlerType = Callable[[Request], Generator[Any, Any, Response]]


class Route:
    def __init__(
        self,
        method: str,
        path: str,
        handler: HandlerType,
    ) -> None:
        self.method = method.upper()
        self.path = path
        self.handler = handler

    def match(self, path: str, method: str) -> bool:
        return self.method == method and self.path == path

    def __repr__(self) -> str:
        return f"<Route {self.method} {self.path} {self.handler}>"


class Router:
    def __init__(self) -> None:
        self.routes: list[Route] = []

    def add_route(self, route: Route) -> None:
        self.routes.append(route)

    def _add(
        self,
        method: str,
        path: str,
        handler: HandlerType,
    ) -> None:
        return self.add_route(Route(method, path, handler))

    def _handler_wrapper(
        self,
        method: str,
        path: str,
    ) -> Callable[[HandlerType], HandlerType]:
        def inner(
            handler: HandlerType,
        ) -> HandlerType:
            self.add_route(Route(method, path, handler))  # type: ignore
            return handler

        return inner

    def match(self, method: str, path: str) -> Route:
        method = method.upper()
        for route in self.routes:
            if route.match(path, method):
                return route
        raise RouteNotFound(path)

    def get(
        self,
        path: str,
    ) -> Callable[[HandlerType], HandlerType]:
        return self._handler_wrapper("GET", path)

    def post(
        self,
        path: str,
    ) -> Callable[[HandlerType], HandlerType]:
        return self._handler_wrapper("POST", path)

    def put(
        self,
        path: str,
    ) -> Callable[[HandlerType], HandlerType]:
        return self._handler_wrapper("PUT", path)

    def delete(
        self,
        path: str,
    ) -> Callable[[HandlerType], HandlerType]:
        return self._handler_wrapper("DELETE", path)

    def patch(
        self,
        path: str,
    ) -> Callable[[HandlerType], HandlerType]:
        return self._handler_wrapper("PATCH", path)


class Server:
    def __init__(
        self,
        default_headers: dict[str, str] | None = None,
    ) -> None:
        self.router = Router()
        self.default_headers = default_headers or {"Server": "gensyncio/0.1"}
        self.socket = GenSocket(socket.AF_INET, socket.SOCK_STREAM)

    def run(
        self,
        host: str = "127.0.0.1",
        port: int = 8080,
        queue_size: int = 5,
    ) -> Generator[None, None, None]:
        loop = get_running_loop()
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((host, port))
        self.socket.listen(queue_size)
        logging.info("Listening started on %s:%s", host, port)
        while True:
            try:
                sock, addr = yield from self.socket.accept()
                loop.create_task(self.process_request(sock, addr))
            except KeyboardInterrupt:
                break
        self.socket.close()

    def process_request(self, socket: GenSocket, addr: Tuple[str, int]):
        http_message = yield from parse_http_message(socket, chunk_size=1024)
        method, path, http_ver = http_message.status_line.split(" ", 2)

        req = Request(
            http_version=http_ver,
            path=path,
            method=method,
            headers=http_message.headers,
            read_body=http_message.read_body,
            body_reader=socket,
            peer_addr=addr,
        )
        yield from socket.wait_writable()
        try:
            route = self.router.match(req.method, req.path)
        except RouteNotFound:
            route = None

        if route is None:
            resp = Response(status=404, reason="Not Found")
            self.reply(req, resp, socket)
            return

        try:
            resp = yield from route.handler(req)
        except Exception as e:
            logger.error(e, exc_info=True)
            resp = Response(status=500, reason="Internal Server Error")

        self.reply(req, resp, socket)
        return

    def reply(self, req: Request, resp: Response, socket: GenSocket) -> None:
        resp.set_http_version(req.http_version)
        socket.send(bytes(resp))
        logger.info(f"{req.method} {req.path} {resp.status}")
