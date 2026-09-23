from __future__ import annotations

import ctypes
from dataclasses import replace
import queue
import sys
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from autoclicker.engine import Runner
from autoclicker.model import Script, ScriptStore, Step
from autoclicker.overlay import MarkerOverlay


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
        self.loop = tk.BooleanVar(value=True)
        self.time_limit = tk.StringVar(value="0")
        self.timer = tk.StringVar(value="Elapsed 00:00.0")
        self.timer_phase = "idle"
        self.countdown_remaining = 3
        self.run_id = 0
        self.active_limit = 0
        self.controls: tk.Toplevel | None = None
        self.controls_pause: ttk.Button | None = None
        self.x = tk.StringVar(value="0")
        self.y = tk.StringVar(value="0")
        self.radius = tk.StringVar(value="24")
        self.hold = tk.StringVar(value="0")
        self.wait = tk.StringVar(value="100")
        self.button = tk.StringVar(value="left")
        self.status = tk.StringVar(value="Ready · F8 captures cursor · F9 stops · F10 pauses")
        self.show_markers = tk.BooleanVar(value=True)
        self.edit_markers = tk.BooleanVar(value=True)
        self.selected_step: int | None = None
        self._build()
        self.overlay = MarkerOverlay(root, self._select_step, self.status.set, self._move_step)
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
        self.root.geometry("700x770")
        frame = ttk.Frame(self.root, padding=16)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Saved scripts").grid(row=0, column=0, sticky="w")
        self.saved = tk.Listbox(frame, height=4, exportselection=False)
        self.saved.grid(row=1, column=0, columnspan=4, sticky="nsew")
        ttk.Button(frame, text="Load", command=self._load).grid(row=2, column=0, sticky="ew")
        ttk.Button(frame, text="Delete", command=self._delete).grid(row=2, column=1, sticky="ew")
        ttk.Label(frame, text="Name").grid(row=3, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.name).grid(row=3, column=1, columnspan=3, sticky="ew")
        ttk.Label(frame, text="Repetitions (when loop is off)").grid(row=4, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.repetitions, width=12).grid(row=4, column=1, sticky="w")
        ttk.Checkbutton(frame, text="Loop until stopped (default)", variable=self.loop).grid(row=4, column=2, columnspan=2, sticky="w")
        ttk.Label(frame, text="Steps, in order (select a row or numbered crosshair to edit)").grid(row=5, column=0, columnspan=4, sticky="w", pady=(14, 0))
        self.step_list = tk.Listbox(frame, height=8, exportselection=False)
        self.step_list.grid(row=6, column=0, columnspan=4, sticky="nsew")
        self.step_list.bind("<<ListboxSelect>>", self._on_list_select)
        ttk.Button(frame, text="Remove selected step", command=self._remove_step).grid(row=7, column=0, columnspan=2, sticky="ew")
        ttk.Button(frame, text="Update selected step", command=self._update_step).grid(row=7, column=2, columnspan=2, sticky="ew")
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
        ttk.Button(frame, text="Save script", command=self._save).grid(row=15, column=0, sticky="ew", pady=(12, 0))
        ttk.Button(frame, text="Start (3s countdown)", command=self._start).grid(row=15, column=1, sticky="ew", pady=(12, 0))
        self.pause_button = ttk.Button(frame, text="Pause (F10)", command=self._toggle_pause)
        self.pause_button.grid(row=15, column=2, sticky="ew", pady=(12, 0))
        ttk.Button(frame, text="STOP (F9)", command=self._stop).grid(row=15, column=3, sticky="ew", pady=(12, 0))
        ttk.Checkbutton(frame, text="Show numbered crosshairs", variable=self.show_markers,
                        command=self._marker_visibility).grid(row=16, column=0, columnspan=2, sticky="w")
        ttk.Checkbutton(frame, text="Select crosshairs on screen", variable=self.edit_markers,
                        command=self._marker_mode).grid(row=16, column=2, columnspan=2, sticky="w")
        ttk.Label(frame, text="Run timer seconds (0 = unlimited)").grid(row=17, column=0, columnspan=2, sticky="w", pady=(8, 0))
        ttk.Entry(frame, textvariable=self.time_limit, width=12).grid(row=17, column=2, sticky="w", pady=(8, 0))
        ttk.Label(frame, textvariable=self.timer).grid(row=18, column=0, columnspan=4, sticky="w", pady=(8, 0))
        ttk.Label(frame, textvariable=self.status, wraplength=650).grid(row=19, column=0, columnspan=4, sticky="w", pady=(8, 0))
        ttk.Label(frame, text="Drag a numbered crosshair to move its click position, then save the script. Radius is visual; clicks go to the center pixel. Turn off selection to use other apps. F9 stops; F10 pauses or resumes.", wraplength=650).grid(row=20, column=0, columnspan=4, sticky="w")
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
        if self.selected_step is not None and self.selected_step < len(self.steps):
            self.step_list.selection_set(self.selected_step)
        else:
            self.selected_step = None
        self.overlay.set_steps(self.steps, self.selected_step)

    def _select_step(self, index: int) -> None:
        if self.worker and self.worker.is_alive():
            return
        if not 0 <= index < len(self.steps):
            return
        self.selected_step = index
        step = self.steps[index]
        for variable, value in ((self.x, step.x), (self.y, step.y),
                                (self.radius, step.radius), (self.hold, step.hold_ms),
                                (self.wait, step.wait_ms)):
            variable.set(str(value))
        self.button.set(step.button)
        self.step_list.selection_clear(0, tk.END)
        self.step_list.selection_set(index)
        self.step_list.see(index)
        self.overlay.select(index)
        self.status.set(f"Editing crosshair {index + 1}; click Update selected step to apply changes")

    def _on_list_select(self, _event) -> None:
        selection = self.step_list.curselection()
        if selection:
            self._select_step(selection[0])

    def _move_step(self, index: int, x: int, y: int) -> None:
        if self.worker and self.worker.is_alive():
            return
        try:
            self.steps[index] = replace(self.steps[index], x=x, y=y)
        except ValueError as exc:
            self.overlay.set_steps(self.steps, self.selected_step)
            self.status.set(f"Cannot move crosshair: {exc}")
            return
        self.selected_step = index
        self._refresh_steps()
        self._select_step(index)
        self.status.set(f"Moved crosshair {index + 1} to ({x}, {y}); save the script to keep it")

    def _marker_visibility(self) -> None:
        self.overlay.set_visible(self.show_markers.get())

    def _marker_mode(self) -> None:
        if self.worker and self.worker.is_alive() and self.edit_markers.get():
            self.edit_markers.set(False)
            self.status.set("Crosshair selection is disabled during playback")
            return
        self.overlay.set_editable(self.edit_markers.get())

    def _step_from_fields(self) -> Step:
        return Step(int(self.x.get()), int(self.y.get()), int(self.radius.get()),
                    int(self.hold.get()), int(self.wait.get()), self.button.get())

    def _update_step(self) -> None:
        if self.worker and self.worker.is_alive():
            return
        if self.selected_step is None:
            self.status.set("Select a numbered crosshair or step first")
            return
        try:
            self.steps[self.selected_step] = self._step_from_fields()
            self._refresh_steps()
            self.status.set(f"Updated crosshair {self.selected_step + 1}; save the script to keep it")
        except ValueError as exc:
            messagebox.showerror("Invalid step", str(exc))

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
        self.loop.set(script.loop)
        self.time_limit.set(str(script.time_limit_seconds))
        self.steps = list(script.steps)
        self.selected_step = None
        self._refresh_steps()

    def _save(self) -> None:
        try:
            script = self._script_from_fields()
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
            self.steps.append(self._step_from_fields())
            self.selected_step = len(self.steps) - 1
            self._refresh_steps()
        except ValueError as exc:
            messagebox.showerror("Invalid step", str(exc))

    def _remove_step(self) -> None:
        if self.selected_step is not None:
            self.steps.pop(self.selected_step)
            self.selected_step = None
            self._refresh_steps()

    def _capture(self) -> None:
        x, y = self.mouse.position
        self.x.set(str(x))
        self.y.set(str(y))
        self.status.set(f"Captured ({x}, {y})")

    def _script_from_fields(self) -> Script:
        return Script(self.name.get().strip(), int(self.repetitions.get()), tuple(self.steps),
                      loop=self.loop.get(), time_limit_seconds=int(self.time_limit.get()))

    def _show_controls(self) -> None:
        self._hide_controls()
        controls = tk.Toplevel(self.root)
        self.controls = controls
        controls.title("AutoClicker playback")
        controls.attributes("-topmost", True)
        controls.resizable(False, False)
        controls.geometry(f"330x98+{max(0, controls.winfo_screenwidth() - 350)}+48")
        controls.protocol("WM_DELETE_WINDOW", self._stop)
        content = ttk.Frame(controls, padding=10)
        content.pack(fill="both", expand=True)
        ttk.Label(content, textvariable=self.timer).pack(anchor="w")
        buttons = ttk.Frame(content)
        buttons.pack(fill="x", pady=(8, 0))
        self.controls_pause = ttk.Button(buttons, text="Pause (F10)", command=self._toggle_pause)
        self.controls_pause.pack(side="left", expand=True, fill="x")
        ttk.Button(buttons, text="Stop (F9)", command=self._stop).pack(side="left", expand=True, fill="x")

    def _hide_controls(self) -> None:
        if self.controls is not None:
            self.controls.destroy()
            self.controls = None
            self.controls_pause = None

    @staticmethod
    def _format_time(seconds: float) -> str:
        tenths = max(0, int(seconds * 10))
        minutes, remainder = divmod(tenths, 600)
        hours, minutes = divmod(minutes, 60)
        return (f"{hours:02}:{minutes:02}:{remainder // 10:02}.{remainder % 10}"
                if hours else f"{minutes:02}:{remainder // 10:02}.{remainder % 10}")

    def _start(self) -> None:
        if self.worker and self.worker.is_alive():
            self.status.set("A script is already running")
            return
        try:
            script = self._script_from_fields()
        except ValueError as exc:
            messagebox.showerror("Invalid script", str(exc))
            return
        self.runner.reset()
        self.run_id += 1
        self.active_limit = script.time_limit_seconds
        run_id = self.run_id
        self.timer_phase = "countdown"
        self.countdown_remaining = 3
        self.timer.set("Starts in 3s · elapsed 00:00.0")
        self.pause_button.configure(text="Pause (F10)")
        self.overlay.set_editable(False)
        self._show_controls()
        self.status.set("Starting in 3 seconds; move to the target window. F10 pauses; F9 stops.")

        def emit(kind: str, value: object) -> None:
            self.events.put((kind, (run_id, value)))

        def work() -> None:
            try:
                count = self.runner.run(script, progress=lambda n, total: emit("progress", (n, total)),
                                        step_changed=lambda index: emit("step", index),
                                        countdown=lambda remaining: emit("countdown", remaining),
                                        started=lambda: emit("started", None))
                emit("done", (count, self.runner.outcome))
            except Exception as exc:
                emit("error", str(exc))

        self.worker = threading.Thread(target=work, daemon=True)
        self.worker.start()

    def _stop(self) -> None:
        if not self.worker or not self.worker.is_alive():
            return
        self.runner.stop()
        self.status.set("Stopping…")

    def _toggle_pause(self) -> None:
        if not self.worker or not self.worker.is_alive():
            return
        if self.runner.pause_event.is_set():
            self.runner.resume()
            self.pause_button.configure(text="Pause (F10)")
            if self.controls_pause:
                self.controls_pause.configure(text="Pause (F10)")
            self.status.set("Resumed · F10 pauses · F9 stops")
        else:
            self.runner.pause()
            self.pause_button.configure(text="Resume (F10)")
            if self.controls_pause:
                self.controls_pause.configure(text="Resume (F10)")
            self.status.set("Paused · F10 resumes · F9 stops")

    def _on_key(self, key) -> None:
        if key == self.keyboard.Key.f8:
            self.events.put(("capture", None))
        elif key == self.keyboard.Key.f9:
            if self.worker and self.worker.is_alive():
                self.runner.stop()
                self.events.put(("stopping", None))
        elif key == self.keyboard.Key.f10:
            self.events.put(("toggle_pause", None))

    def _poll(self) -> None:
        while not self.events.empty():
            kind, value = self.events.get()
            if kind == "capture":
                self._capture()
            elif kind == "stopping":
                self.status.set("Stopping…")
            elif kind == "toggle_pause":
                self._toggle_pause()
            elif value[0] != self.run_id:
                continue
            elif kind == "countdown":
                self.countdown_remaining = value[1]
            elif kind == "started":
                self.timer_phase = "running"
            elif kind == "progress":
                done, total = value[1]
                self.status.set(f"Clicked {done}" + (" · looping" if total is None else f" / {total}") +
                                " · F10 pauses · F9 stops")
            elif kind == "step":
                self.overlay.highlight(value[1])
            elif kind == "done":
                count, outcome = value[1]
                self.timer_phase = "done"
                self._hide_controls()
                self.pause_button.configure(text="Pause (F10)")
                self.overlay.highlight(None)
                self.overlay.set_editable(self.edit_markers.get())
                label = {"timer": "Timer ended", "stopped": "Stopped", "completed": "Finished"}[outcome]
                self.status.set(f"{label} after {count} clicks")
            elif kind == "error":
                self.timer_phase = "done"
                self._hide_controls()
                self.pause_button.configure(text="Pause (F10)")
                self.overlay.highlight(None)
                self.overlay.set_editable(self.edit_markers.get())
                self.status.set(f"Input error: {value[1]}")
        if self.timer_phase == "countdown":
            self.timer.set(f"Starts in {self.countdown_remaining}s" +
                           (" · paused" if self.runner.pause_event.is_set() else "") +
                           " · elapsed 00:00.0")
        elif self.timer_phase in ("running", "done"):
            elapsed = self.runner.elapsed()
            limit = self.active_limit
            self.timer.set(f"Elapsed {self._format_time(elapsed)}" +
                           (f" · remaining {self._format_time(limit - elapsed)}" if limit else "") +
                           (" · paused" if self.timer_phase == "running" and self.runner.pause_event.is_set() else ""))
        self.root.after(50, self._poll)

    def _close(self) -> None:
        self.runner.stop()
        self.listener.stop()
        self._hide_controls()
        self.overlay.destroy()
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
