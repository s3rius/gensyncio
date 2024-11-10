from typing import Any


class Undefined:
    """Undefined value if nothing was set."""


class Future:
    def __init__(self) -> None:
        self.result: Any = Undefined

    def done(self) -> bool:
        """Check if the future is done."""
        return bool(self.result != Undefined)

    def set_result(self, result: Any) -> None:
        """Set the result of the future."""
        self.result = result

    def __iter__(self) -> "Future":
        """Return self as an iterator."""
        return self

    def __next__(self) -> None:
        """Return the result if done, otherwise None."""
        if self.done():
            raise StopIteration(self.result)
        return None
