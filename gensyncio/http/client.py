from typing import Any, Generator
import socket
from urllib import parse
from json import dumps as json_dumps, loads as json_loads

from gensyncio.gensocket import GenSocket
from gensyncio.http.parser import parse_http_message


class ClientResponse:
    def __init__(
        self,
        status_line: str,
        headers: dict[str, bytes],
        body: bytearray,
    ) -> None:
        self.http_version, self.status_full = status_line.split(" ", 1)
        self.status = int(self.status_full.split(" ", 1)[0])
        self.headers = headers
        self.body = bytes(body)

    @property
    def json(self) -> Any:
        return json_loads(self.body)

    def __repr__(self) -> str:
        return f"<ClientResponse {self.http_version} {self.status}>"


class ClientRequest:
    def __init__(
        self,
        url: str,
        method: str,
        data: bytes | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
        *,
        json: Any = None,
    ) -> None:
        self.method = method
        self.data = data or b""
        self.headers = headers or {}
        if json is not None:
            self.data = json_dumps(json).encode("utf-8")
            self.headers["Content-Type"] = "application/json"
        scheme, self.netloc, self.path, self.params, self.query, self.fragment = (
            parse.urlparse(url)
        )
        self.path = self.path or "/"
        self.tls = scheme == "https"
        self.port = 443 if self.tls else 80
        if self.netloc.find(":") != -1:
            self.netloc, port = self.netloc.split(":")
            self.port = int(port)
        self.socket = GenSocket(socket.AF_INET, socket.SOCK_STREAM)
        if timeout:
            self.socket.settimeout(timeout)

    def send(self) -> Generator[None, None, ClientResponse]:
        yield from self.socket.connect((self.netloc, self.port))
        self.socket.send(f"{self.method} {self.path} HTTP/1.1\r\n".encode("utf-8"))
        headers = self.headers.copy()
        headers["Host"] = self.netloc
        headers["Content-Length"] = str(len(self.data))
        for h_name, h_val in headers.items():
            self.socket.send(f"{h_name}: {h_val}\r\n".encode("utf-8"))
        if self.data:
            self.socket.send(b"\r\n")
            self.socket.send(self.data)
        # Wait for the response to be ready
        yield from self.socket.wait_readable()
        parsed = yield from parse_http_message(self.socket)
        body = parsed.read_body
        content_length = int(parsed.headers["content-length"])
        while len(body) < content_length:
            data = yield from self.socket.recv(1024)
            if not data:
                break
            body.extend(data)
        return ClientResponse(
            status_line=parsed.status_line,
            headers=parsed.headers,
            body=body,
        )
