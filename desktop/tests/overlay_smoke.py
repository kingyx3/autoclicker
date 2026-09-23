"""Run with xvfb-run to check marker opacity, dragging and input mode."""

import tkinter as tk

from autoclicker.model import Step
from autoclicker.overlay import MarkerOverlay


root = tk.Tk()
root.geometry("400x300+0+0")
root.update()
selected = []
errors = []
moved = []
overlay = MarkerOverlay(root, selected.append, errors.append,
                        lambda index, x, y: moved.append((index, x, y)))
overlay.set_steps([Step(80, 90, radius=35), Step(180, 190, radius=12)])
root.update()
assert len(overlay.windows) == 2
assert overlay.windows[0][0].winfo_width() == 80
# Xvfb has no compositor, so its reported alpha is not a visual opacity check.
overlay.windows[1][1].event_generate("<ButtonPress-1>", rootx=180, rooty=190)
overlay.windows[1][1].event_generate("<ButtonRelease-1>", rootx=180, rooty=190)
root.update()
assert selected == [1]
assert moved == []
canvas = overlay.windows[0][1]
canvas.event_generate("<ButtonPress-1>", rootx=80, rooty=90)
canvas.event_generate("<B1-Motion>", rootx=110, rooty=115)
root.update()
canvas.event_generate("<ButtonRelease-1>", rootx=110, rooty=115)
root.update()
assert selected == [1, 0]
assert moved == [(0, 110, 115)]
overlay.select(1)
overlay.set_editable(False)
root.update()
assert not errors, errors
overlay.set_editable(True)
root.update()
assert overlay.windows[0][0].winfo_viewable()
overlay.destroy()
root.destroy()
