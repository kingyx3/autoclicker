from __future__ import annotations

import threading
import time
import math
from typing import Callable, Protocol

from .model import Script


class Mouse(Protocol):
    position: tuple[int, int]

    def click(self, button: object) -> None: ...
    def press(self, button: object) -> None: ...
    def release(self, button: object) -> None: ...


class Runner:
    """Replay steps until stopped, timed out, or the finite count completes."""

    def __init__(self, mouse: Mouse, buttons: dict[str, object]):
        self.mouse = mouse
        self.buttons = buttons
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        self._clock_lock = threading.Lock()
        self._started = False
        self._active_since: float | None = None
        self._active_seconds = 0.0
        self._time_limit = 0
        self.outcome = "ready"

    def stop(self) -> None:
        self.stop_event.set()

    def reset(self) -> None:
        self.stop_event.clear()
        self.pause_event.clear()
        with self._clock_lock:
            self._started = False
            self._active_since = None
            self._active_seconds = 0.0
        self.outcome = "ready"

    def pause(self) -> None:
        with self._clock_lock:
            if self.pause_event.is_set() or self.stop_event.is_set():
                return
            if self._active_since is not None:
                self._active_seconds += time.monotonic() - self._active_since
                self._active_since = None
            self.pause_event.set()

    def resume(self) -> None:
        with self._clock_lock:
            if not self.pause_event.is_set():
                return
            self.pause_event.clear()
            if self._started:
                self._active_since = time.monotonic()

    def elapsed(self) -> float:
        with self._clock_lock:
            return self._active_seconds + (time.monotonic() - self._active_since
                                           if self._active_since is not None else 0.0)

    def _start_clock(self) -> None:
        with self._clock_lock:
            self._started = True
            if not self.pause_event.is_set():
                self._active_since = time.monotonic()

    def _wait(self, seconds: float, *, interrupt_on_pause: bool = False,
              countdown: Callable[[int], None] | None = None) -> str:
        remaining = seconds
        last_countdown = -1
        while True:
            if self.stop_event.is_set():
                return "stopped"
            if self._time_limit and self.elapsed() >= self._time_limit:
                return "timer"
            if self.pause_event.is_set():
                if interrupt_on_pause:
                    return "paused"
                self.stop_event.wait(0.03)
                continue
            count = math.ceil(remaining)
            if countdown and count != last_countdown:
                countdown(count)
                last_countdown = count
            if remaining <= 0:
                return "complete"
            start = time.monotonic()
            if self.stop_event.wait(min(remaining, 0.03)):
                return "stopped"
            if not self.pause_event.is_set():
                remaining -= time.monotonic() - start

    def _finish(self, outcome: str, completed: int) -> int:
        with self._clock_lock:
            if self._active_since is not None:
                self._active_seconds += time.monotonic() - self._active_since
                self._active_since = None
            self._started = False
        self.outcome = outcome
        return completed

    def run(self, script: Script, *, start_delay: float = 3.0,
            progress: Callable[[int, int | None], None] | None = None,
            step_changed: Callable[[int], None] | None = None,
            countdown: Callable[[int], None] | None = None,
            started: Callable[[], None] | None = None) -> int:
        completed = 0
        total = None if script.loop else len(script.steps) * script.repetitions
        last_highlight = 0.0
        self._time_limit = script.time_limit_seconds
        result = self._wait(start_delay, countdown=countdown)
        if result != "complete":
            return self._finish(result, completed)
        self._start_clock()
        if started:
            started()
        cycles = 0
        while script.loop or cycles < script.repetitions:
            for index, step in enumerate(script.steps):
                while True:
                    result = self._wait(0)
                    if result != "complete":
                        return self._finish(result, completed)
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
                            result = self._wait(step.hold_ms / 1000, interrupt_on_pause=True)
                        finally:
                            if pressed:
                                self.mouse.release(button)
                        if result == "paused":
                            continue  # Release immediately; restart this hold after resume.
                        if result != "complete":
                            return self._finish(result, completed)
                    break
                completed += 1
                if progress and (completed == 1 or completed % 50 == 0 or
                                 (total is not None and completed == total)):
                    progress(completed, total)
                result = self._wait(step.wait_ms / 1000)
                if result != "complete":
                    return self._finish(result, completed)
            cycles += 1
        return self._finish("completed", completed)
