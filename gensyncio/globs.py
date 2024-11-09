from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gensyncio.loop import Loop


RUNNING_LOOP = None


def get_running_loop() -> "Loop":
    global RUNNING_LOOP
    if RUNNING_LOOP is None:
        raise RuntimeError("No running loop")
    return RUNNING_LOOP


def set_running_loop(loop: "Loop") -> None:
    global RUNNING_LOOP
    RUNNING_LOOP = loop
