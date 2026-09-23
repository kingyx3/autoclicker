"""Run with xvfb-run to check marker creation, selection and input mode."""

import tkinter as tk

from autoclicker.model import Step
from autoclicker.overlay import MarkerOverlay


root = tk.Tk()
root.geometry("400x300+0+0")
root.update()
selected = []
errors = []
overlay = MarkerOverlay(root, selected.append, errors.append)
overlay.set_steps([Step(80, 90, radius=35), Step(180, 190, radius=12)])
root.update()
assert len(overlay.windows) == 2
assert overlay.windows[0][0].winfo_width() == 80
overlay.windows[1][1].event_generate("<Button-1>")
root.update()
assert selected == [1]
overlay.select(1)
overlay.set_editable(False)
root.update()
assert not errors, errors
overlay.set_editable(True)
root.update()
assert overlay.windows[0][0].winfo_viewable()
overlay.destroy()
root.destroy()
