import dataclasses
import enum
import io
from typing import Generator

from gensyncio.gensocket import GenSocket


class ParserState(enum.Enum):
    STATUS_LINE = enum.auto()
    HEADERS = enum.auto()
    BODY = enum.auto()

    def next(self) -> "ParserState":
        if self == ParserState.STATUS_LINE:
            return ParserState.HEADERS
        if self == ParserState.HEADERS:
            return ParserState.BODY
        return self


@dataclasses.dataclass
class ParsedHTTPMesaage:
    status_line: str
    headers: dict[str, bytes]
    read_body: bytearray


def parse_http_message(
    sock: GenSocket,
    chunk_size: int = 1024,
) -> Generator[None, None, ParsedHTTPMesaage]:
    status_line = bytearray()
    headers = bytearray()
    body = bytearray()
    headers_val = {}
    state = ParserState.STATUS_LINE
    while True:
        data = yield from sock.recv(chunk_size)
        if not data:
            break
        data_io = io.BytesIO(data)
        for line in data_io.readlines():
            if state == ParserState.STATUS_LINE:
                status_line.extend(line)
                if b"\r\n" in status_line:
                    state = state.next()
                    continue
            elif state == ParserState.HEADERS:
                headers.extend(line)
                if b"\r\n\r\n" in headers:
                    state = state.next()
            else:
                body.extend(line)

        if state == ParserState.BODY:
            break

    for header in headers.split(b"\r\n"):
        if not header:
            continue
        key, value = header.split(b":", 1)
        headers_val[key.strip().lower().decode("utf-8")] = bytes(value.strip())

    return ParsedHTTPMesaage(
        status_line=status_line.strip().decode("utf-8"),
        headers=headers_val,
        read_body=body,
    )
