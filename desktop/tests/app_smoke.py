"""Exercise the desktop countdown, playback panel and pause/stop under Xvfb."""

import os
import tempfile
import time
import tkinter as tk

from main import App


class FakeController:
    position = (0, 0)

    def click(self, _button):
        pass

    def press(self, _button):
        pass

    def release(self, _button):
        pass


class MouseModule:
    Controller = FakeController

    class Button:
        left = "left"
        right = "right"
        middle = "middle"


class KeyboardModule:
    class Key:
        f8 = "f8"
        f9 = "f9"
        f10 = "f10"

    class Listener:
        def __init__(self, on_press):
            self.on_press = on_press

        def start(self):
            pass

        def stop(self):
            pass


with tempfile.TemporaryDirectory() as folder:
    os.environ["XDG_CONFIG_HOME"] = folder
    root = tk.Tk()
    app = App(root, MouseModule, KeyboardModule)
    app.name.set("smoke")
    app.x.set("450")
    app.y.set("450")
    app._add_step()
    assert app.loop.get()
    app._start()
    root.update()
    assert app.controls is not None and app.controls.winfo_viewable()
    assert app.timer_phase == "countdown"
    app._toggle_pause()
    assert app.runner.pause_event.is_set()
    assert "Resume" in app.controls_pause.cget("text")
    app._toggle_pause()
    assert not app.runner.pause_event.is_set()
    app._stop()
    deadline = time.monotonic() + 2
    while app.controls is not None and time.monotonic() < deadline:
        root.update()
        time.sleep(0.02)
    assert app.controls is None
    assert "Stopped" in app.status.get()
    app._close()
