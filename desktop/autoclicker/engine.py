from __future__ import annotations

import threading
import time
from typing import Callable, Protocol

from .model import Script


class Mouse(Protocol):
    position: tuple[int, int]

    def click(self, button: object) -> None: ...
    def press(self, button: object) -> None: ...
    def release(self, button: object) -> None: ...


class Runner:
    """Run a finite script on a worker thread; all waits can be interrupted."""

    def __init__(self, mouse: Mouse, buttons: dict[str, object]):
        self.mouse = mouse
        self.buttons = buttons
        self.stop_event = threading.Event()

    def stop(self) -> None:
        self.stop_event.set()

    def reset(self) -> None:
        self.stop_event.clear()

    def run(self, script: Script, *, start_delay: float = 3.0,
            progress: Callable[[int, int], None] | None = None,
            step_changed: Callable[[int], None] | None = None) -> int:
        completed = 0
        total = len(script.steps) * script.repetitions
        last_highlight = 0.0
        if self.stop_event.wait(start_delay):
            return completed
        for _ in range(script.repetitions):
            for index, step in enumerate(script.steps):
                if self.stop_event.is_set():
                    return completed
                now = time.monotonic()
                if step_changed and (completed == 0 or now - last_highlight >= 0.05):
                    step_changed(index)
                    last_highlight = now
                button = self.buttons[step.button]
                self.mouse.position = (step.x, step.y)
                if step.hold_ms == 0:
                    self.mouse.click(button)
                else:
                    pressed = False
                    try:
                        self.mouse.press(button)
                        pressed = True
                        self.stop_event.wait(step.hold_ms / 1000)
                    finally:
                        if pressed:
                            self.mouse.release(button)
                completed += 1
                if progress and (completed == 1 or completed % 50 == 0 or completed == total):
                    progress(completed, total)
                if self.stop_event.wait(step.wait_ms / 1000):
                    return completed
        return completed
