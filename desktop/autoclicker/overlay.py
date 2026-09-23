"""Screen markers for the currently edited desktop script.

All Tk operations here run on the UI thread. During playback, platform input
regions make the markers transparent to mouse events; if that fails, markers
are hidden so they cannot intercept automated clicks.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import sys
import tkinter as tk
from collections.abc import Callable

from .model import Step


MAGENTA = "#ff00ff"


class MarkerOverlay:
    def __init__(self, root: tk.Tk, on_select: Callable[[int], None],
                 on_error: Callable[[str], None]):
        self.root = root
        self.on_select = on_select
        self.on_error = on_error
        self.windows: list[tuple[tk.Toplevel, tk.Canvas, int]] = []
        self.steps: list[Step] = []
        self.selected: int | None = None
        self.active: int | None = None
        self.visible = True
        self.editable = True

    def set_steps(self, steps: list[Step], selected: int | None = None) -> None:
        self.destroy()
        self.steps = list(steps)
        self.selected = selected
        if not self.visible:
            return
        for index, step in enumerate(steps):
            radius = step.radius
            size = max(2 * radius + 10, 38)
            center = size // 2
            window = tk.Toplevel(self.root)
            window.withdraw()
            window.title(f"AutoClicker marker {index + 1}")
            window.overrideredirect(True)
            window.attributes("-topmost", True)
            if sys.platform == "win32":
                window.configure(background=MAGENTA)
                window.attributes("-transparentcolor", MAGENTA)
            else:
                window.attributes("-alpha", 0.8)
            window.geometry(f"{size}x{size}+{step.x - center}+{step.y - center}")
            canvas = tk.Canvas(window, width=size, height=size, highlightthickness=0,
                               background=MAGENTA if sys.platform == "win32" else "#152235")
            canvas.pack()
            canvas.create_oval(center - radius, center - radius, center + radius,
                               center + radius, width=2, tags="marker")
            canvas.create_line(center - radius, center, center + radius, center,
                               width=2, tags="marker")
            canvas.create_line(center, center - radius, center, center + radius,
                               width=2, tags="marker")
            canvas.create_text(center, center, text=str(index + 1), fill="white",
                               font=("TkDefaultFont", 12, "bold"), tags="number")
            canvas.bind("<Button-1>", lambda _event, n=index: self.on_select(n))
            window.deiconify()
            self.windows.append((window, canvas, index))
        self._colorize()
        self._apply_input_mode()

    def set_visible(self, visible: bool) -> None:
        if self.visible != visible:
            self.visible = visible
            self.set_steps(self.steps, self.selected)

    def set_editable(self, editable: bool) -> None:
        self.editable = editable
        self._apply_input_mode()

    def select(self, index: int | None) -> None:
        self.selected = index
        self._colorize()

    def highlight(self, index: int | None) -> None:
        self.active = index
        self._colorize()

    def _colorize(self) -> None:
        for _window, canvas, index in self.windows:
            color = "#ff6148" if index == self.active else "#30d9a5" if index == self.selected else "#47b7ff"
            canvas.itemconfigure("marker", fill=color)

    def _apply_input_mode(self) -> None:
        for window, _canvas, _index in self.windows:
            try:
                window.deiconify()
                self._set_click_through(window, not self.editable)
            except (OSError, RuntimeError, ImportError, AttributeError) as exc:
                if not self.editable:
                    window.withdraw()
                    self.on_error(f"Overlay hidden during playback: click-through unavailable ({exc})")

    @staticmethod
    def _set_click_through(window: tk.Toplevel, enabled: bool) -> None:
        window.update_idletasks()
        if sys.platform == "win32":
            user32 = ctypes.windll.user32
            user32.GetParent.argtypes = [ctypes.c_void_p]
            user32.GetParent.restype = ctypes.c_void_p
            hwnd = user32.GetParent(window.winfo_id()) or window.winfo_id()
            get_style = user32.GetWindowLongPtrW
            set_style = user32.SetWindowLongPtrW
            get_style.argtypes = [ctypes.c_void_p, ctypes.c_int]
            get_style.restype = ctypes.c_ssize_t
            set_style.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_ssize_t]
            set_style.restype = ctypes.c_ssize_t
            style = get_style(hwnd, -20)
            style = (style | 0x80000 | 0x80 | 0x20) if enabled else ((style | 0x80000 | 0x80) & ~0x20)
            set_style(hwnd, -20, style)
            if get_style(hwnd, -20) != style:
                raise OSError("SetWindowLongPtrW failed")
            user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0004 | 0x0020)
        elif sys.platform == "darwin":
            from AppKit import NSApp

            title = window.title()
            matches = [native for native in NSApp.windows() if native.title() == title]
            if not matches:
                raise RuntimeError("native marker window not found")
            matches[-1].setIgnoresMouseEvents_(enabled)
        else:
            display_name = ctypes.util.find_library("X11")
            fixes_name = ctypes.util.find_library("Xfixes")
            if not display_name or not fixes_name:
                raise RuntimeError("X11 XFixes is unavailable")
            x11 = ctypes.CDLL(display_name)
            fixes = ctypes.CDLL(fixes_name)
            x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
            x11.XOpenDisplay.restype = ctypes.c_void_p
            x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
            x11.XFlush.argtypes = [ctypes.c_void_p]
            fixes.XFixesCreateRegion.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int]
            fixes.XFixesCreateRegion.restype = ctypes.c_ulong
            fixes.XFixesDestroyRegion.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
            fixes.XFixesSetWindowShapeRegion.argtypes = [ctypes.c_void_p, ctypes.c_ulong,
                                                         ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                                         ctypes.c_ulong]
            display = x11.XOpenDisplay(None)
            if not display:
                raise RuntimeError("cannot open X11 display")
            try:
                region = fixes.XFixesCreateRegion(display, None, 0) if enabled else 0
                if enabled and not region:
                    raise RuntimeError("cannot create empty X11 input region")
                try:
                    fixes.XFixesSetWindowShapeRegion(display, window.winfo_id(), 2, 0, 0, region)
                    x11.XFlush(display)
                finally:
                    if region:
                        fixes.XFixesDestroyRegion(display, region)
            finally:
                x11.XCloseDisplay(display)

    def destroy(self) -> None:
        for window, _canvas, _index in self.windows:
            window.destroy()
        self.windows.clear()
