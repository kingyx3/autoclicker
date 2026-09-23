from __future__ import annotations

import ctypes
import queue
import sys
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from autoclicker.engine import Runner
from autoclicker.model import Script, ScriptStore, Step


class App:
    def __init__(self, root: tk.Tk, mouse_module, keyboard_module):
        self.root = root
        self.mouse = mouse_module.Controller()
        self.keyboard = keyboard_module
        self.runner = Runner(self.mouse, {
            "left": mouse_module.Button.left,
            "right": mouse_module.Button.right,
            "middle": mouse_module.Button.middle,
        })
        self.worker: threading.Thread | None = None
        self.events: queue.SimpleQueue[tuple[str, object]] = queue.SimpleQueue()
        self.store = ScriptStore()
        self.scripts: list[Script] = []
        self.steps: list[Step] = []
        self.name = tk.StringVar()
        self.repetitions = tk.StringVar(value="1")
        self.x = tk.StringVar(value="0")
        self.y = tk.StringVar(value="0")
        self.radius = tk.StringVar(value="24")
        self.hold = tk.StringVar(value="0")
        self.wait = tk.StringVar(value="100")
        self.button = tk.StringVar(value="left")
        self.status = tk.StringVar(value="Ready · F8 captures cursor · F9 stops")
        self._build()
        try:
            self.scripts = self.store.load()
        except (OSError, ValueError, KeyError, TypeError) as exc:
            messagebox.showerror("Cannot read scripts", str(exc))
        self._refresh_saved()
        self.listener = keyboard_module.Listener(on_press=self._on_key)
        try:
            self.listener.start()
        except Exception as exc:
            self.status.set(f"Keyboard shortcuts unavailable: {exc}")
        self.root.after(50, self._poll)
        self.root.protocol("WM_DELETE_WINDOW", self._close)

    def _build(self) -> None:
        self.root.title("AutoClicker Desktop")
        self.root.geometry("700x710")
        frame = ttk.Frame(self.root, padding=16)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Saved scripts").grid(row=0, column=0, sticky="w")
        self.saved = tk.Listbox(frame, height=4, exportselection=False)
        self.saved.grid(row=1, column=0, columnspan=4, sticky="nsew")
        ttk.Button(frame, text="Load", command=self._load).grid(row=2, column=0, sticky="ew")
        ttk.Button(frame, text="Delete", command=self._delete).grid(row=2, column=1, sticky="ew")
        ttk.Label(frame, text="Name").grid(row=3, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.name).grid(row=3, column=1, columnspan=3, sticky="ew")
        ttk.Label(frame, text="Repetitions").grid(row=4, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.repetitions, width=12).grid(row=4, column=1, sticky="w")
        ttk.Label(frame, text="Steps, in order (select to remove)").grid(row=5, column=0, columnspan=4, sticky="w", pady=(14, 0))
        self.step_list = tk.Listbox(frame, height=8, exportselection=False)
        self.step_list.grid(row=6, column=0, columnspan=4, sticky="nsew")
        ttk.Button(frame, text="Remove selected step", command=self._remove_step).grid(row=7, column=0, columnspan=2, sticky="ew")
        fields = [("X screen pixel", self.x), ("Y screen pixel", self.y),
                  ("Marker radius (visual)", self.radius), ("Hold ms (0 = quick click)", self.hold),
                  ("Wait after click ms", self.wait)]
        for index, (label, variable) in enumerate(fields, start=8):
            ttk.Label(frame, text=label).grid(row=index, column=0, columnspan=2, sticky="w")
            ttk.Entry(frame, textvariable=variable, width=12).grid(row=index, column=2, sticky="w")
        ttk.Label(frame, text="Mouse button").grid(row=13, column=0, sticky="w")
        ttk.Combobox(frame, textvariable=self.button, values=("left", "right", "middle"), state="readonly", width=12).grid(row=13, column=2, sticky="w")
        ttk.Button(frame, text="Capture cursor (F8)", command=self._capture).grid(row=14, column=0, columnspan=2, sticky="ew")
        ttk.Button(frame, text="Add step", command=self._add_step).grid(row=14, column=2, columnspan=2, sticky="ew")
        ttk.Button(frame, text="Save script", command=self._save).grid(row=15, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        ttk.Button(frame, text="Run in 3 seconds", command=self._start).grid(row=15, column=2, sticky="ew", pady=(12, 0))
        ttk.Button(frame, text="STOP (F9)", command=self._stop).grid(row=15, column=3, sticky="ew", pady=(12, 0))
        ttk.Label(frame, textvariable=self.status, wraplength=650).grid(row=16, column=0, columnspan=4, sticky="w", pady=(12, 0))
        ttk.Label(frame, text="The radius labels a target; the OS sends a single mouse click at its center. Keep F9 available while running.", wraplength=650).grid(row=17, column=0, columnspan=4, sticky="w")
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(3, weight=1)
        frame.rowconfigure(6, weight=1)

    def _refresh_saved(self) -> None:
        self.saved.delete(0, tk.END)
        for script in self.scripts:
            self.saved.insert(tk.END, script.name)

    def _refresh_steps(self) -> None:
        self.step_list.delete(0, tk.END)
        for n, step in enumerate(self.steps, 1):
            self.step_list.insert(tk.END, f"{n}. {step.button} ({step.x}, {step.y})  hold {step.hold_ms} ms  wait {step.wait_ms} ms  radius {step.radius}")

    def _selected(self) -> int | None:
        selected = self.saved.curselection()
        return selected[0] if selected else None

    def _load(self) -> None:
        index = self._selected()
        if index is None:
            return
        script = self.scripts[index]
        self.name.set(script.name)
        self.repetitions.set(str(script.repetitions))
        self.steps = list(script.steps)
        self._refresh_steps()

    def _save(self) -> None:
        try:
            script = Script(self.name.get().strip(), int(self.repetitions.get()), tuple(self.steps))
            updated = [s for s in self.scripts if s.name != script.name] + [script]
            self.store.write(updated)
            self.scripts = updated
            self._refresh_saved()
            self.status.set(f"Saved {script.name}")
        except (ValueError, OSError) as exc:
            messagebox.showerror("Cannot save script", str(exc))

    def _delete(self) -> None:
        index = self._selected()
        if index is None or not messagebox.askyesno("Delete script", f"Delete {self.scripts[index].name}?"):
            return
        try:
            updated = [s for i, s in enumerate(self.scripts) if i != index]
            self.store.write(updated)
            self.scripts = updated
            self._refresh_saved()
        except OSError as exc:
            messagebox.showerror("Cannot delete script", str(exc))

    def _add_step(self) -> None:
        try:
            if len(self.steps) >= 100:
                raise ValueError("Maximum 100 steps")
            self.steps.append(Step(int(self.x.get()), int(self.y.get()), int(self.radius.get()),
                                   int(self.hold.get()), int(self.wait.get()), self.button.get()))
            self._refresh_steps()
        except ValueError as exc:
            messagebox.showerror("Invalid step", str(exc))

    def _remove_step(self) -> None:
        selection = self.step_list.curselection()
        if selection:
            self.steps.pop(selection[0])
            self._refresh_steps()

    def _capture(self) -> None:
        x, y = self.mouse.position
        self.x.set(str(x))
        self.y.set(str(y))
        self.status.set(f"Captured ({x}, {y})")

    def _start(self) -> None:
        if self.worker and self.worker.is_alive():
            self.status.set("A script is already running")
            return
        try:
            script = Script(self.name.get().strip(), int(self.repetitions.get()), tuple(self.steps))
        except ValueError as exc:
            messagebox.showerror("Invalid script", str(exc))
            return
        self.runner.reset()
        self.status.set("Starting in 3 seconds; move to the target window. F9 stops.")

        def work() -> None:
            try:
                count = self.runner.run(script, progress=lambda n, total: self.events.put(("progress", (n, total))))
                self.events.put(("done", count))
            except Exception as exc:
                self.events.put(("error", str(exc)))

        self.worker = threading.Thread(target=work, daemon=True)
        self.worker.start()

    def _stop(self) -> None:
        self.runner.stop()
        self.status.set("Stopping…")

    def _on_key(self, key) -> None:
        if key == self.keyboard.Key.f8:
            self.events.put(("capture", None))
        elif key == self.keyboard.Key.f9:
            self.runner.stop()
            self.events.put(("stopping", None))

    def _poll(self) -> None:
        while not self.events.empty():
            kind, value = self.events.get()
            if kind == "capture":
                self._capture()
            elif kind == "stopping":
                self.status.set("Stopping…")
            elif kind == "progress":
                done, total = value
                self.status.set(f"Clicked {done} / {total} · F9 stops")
            elif kind == "done":
                self.status.set(f"Finished or stopped after {value} clicks")
            elif kind == "error":
                self.status.set(f"Input error: {value}")
        self.root.after(50, self._poll)

    def _close(self) -> None:
        self.runner.stop()
        self.listener.stop()
        self.root.destroy()


def main() -> None:
    if sys.platform == "win32":
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except (AttributeError, OSError):
            pass
    root = tk.Tk()
    try:
        from pynput import keyboard, mouse
        App(root, mouse, keyboard)
    except Exception as exc:
        messagebox.showerror("Input unavailable", f"Desktop input could not initialize: {exc}")
        root.destroy()
        return
    root.mainloop()


if __name__ == "__main__":
    main()
