import socket
import select
from typing import Generator
import errno


class GenSocket:
    def __init__(
        self,
        family: int = -1,
        type: int = -1,
        proto: int = -1,
        fileno: None | int = None,
        sock: socket.socket | None = None,
    ) -> None:
        if sock is not None:
            self._inner = sock
        else:
            self._inner = socket.socket(family, type, proto, fileno)
        self._inner.setblocking(False)

    def settimeout(self, timeout: float | None) -> None:
        self._inner.settimeout(timeout)

    def connect(self, address: tuple[str, int]) -> Generator[None, None, None]:
        try:
            self._inner.connect(address)
        except BlockingIOError as err:
            if err.errno != errno.EINPROGRESS:
                raise
        yield from self.wait_writable()

    def send(self, data: bytes, flags: int = 0, /) -> None:
        self._inner.send(data, flags)

    def wait_writable(self) -> Generator[None, None, None]:
        while True:
            _, writable, _ = select.select([], [self], [], 0.01)
            if not writable:
                yield
                continue
            break

    def wait_readable(self) -> Generator[None, None, None]:
        while True:
            readable, _, _ = select.select([self], [], [], 0.01)
            if not readable:
                yield
                continue
            break

    def recv(self, bufsize: int, flags: int = 0, /) -> Generator[None, None, bytes]:
        yield from self.wait_readable()
        while True:
            yield
            try:
                return self._inner.recv(bufsize, flags)
            except socket.timeout:
                raise
            except socket.error as error:
                if error.errno == errno.EAGAIN:
                    continue
                else:
                    raise

    def bind(self, address: tuple[str, int]) -> None:
        self._inner.bind(address)

    def setsockopt(self, level: int, optname: int, value: int | bytes) -> None:
        self._inner.setsockopt(level, optname, value)

    def accept(self) -> Generator[None, None, tuple["GenSocket", tuple[str, int]]]:
        yield from self.wait_readable()
        conn, addr = self._inner.accept()
        return GenSocket(sock=conn), addr

    def listen(self, backlog: int) -> None:
        self._inner.listen(backlog)

    def close(self) -> None:
        self._inner.close()

    def fileno(self) -> int:
        return self._inner.fileno()
