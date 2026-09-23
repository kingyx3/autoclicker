import tempfile
import threading
import unittest
from pathlib import Path

from autoclicker.engine import Runner
from autoclicker.model import Script, ScriptStore, Step


class FakeMouse:
    def __init__(self):
        self.position = (0, 0)
        self.actions = []

    def click(self, button):
        self.actions.append(("click", self.position, button))

    def press(self, button):
        self.actions.append(("press", self.position, button))

    def release(self, button):
        self.actions.append(("release", self.position, button))


class ScriptTests(unittest.TestCase):
    def test_round_trip_and_mobile_format(self):
        script = Script("example", 2, (Step(150, 200, hold_ms=0, wait_ms=1), Step(-50, 10, button="right")))
        with tempfile.TemporaryDirectory() as folder:
            store = ScriptStore(Path(folder) / "scripts.json")
            store.write([script])
            self.assertEqual(store.load(), [script])
            self.assertEqual(script.to_dict()["steps"][0]["holdMs"], 0)

    def test_rejects_invalid_script(self):
        with self.assertRaises(ValueError):
            Script("empty", 1, ())
        with self.assertRaises(ValueError):
            Step(1, 2, hold_ms=-1)

    def test_runs_in_order_and_counts_repetitions(self):
        mouse = FakeMouse()
        runner = Runner(mouse, {"left": "L", "right": "R"})
        script = Script("two points", 2, (Step(1, 2, wait_ms=0), Step(3, 4, wait_ms=0, button="right")))
        self.assertEqual(runner.run(script, start_delay=0), 4)
        self.assertEqual(mouse.actions, [
            ("click", (1, 2), "L"), ("click", (3, 4), "R"),
            ("click", (1, 2), "L"), ("click", (3, 4), "R"),
        ])

    def test_reports_first_crosshair_and_keeps_click_order(self):
        mouse = FakeMouse()
        runner = Runner(mouse, {"left": "L"})
        script = Script("markers", 1, (Step(5, 6, wait_ms=60), Step(7, 8, wait_ms=0)))
        selected = []
        self.assertEqual(runner.run(script, start_delay=0, step_changed=selected.append), 2)
        self.assertEqual(selected, [0, 1])

    def test_stop_releases_held_button(self):
        mouse = FakeMouse()
        runner = Runner(mouse, {"left": "L"})
        script = Script("hold", 10, (Step(1, 2, hold_ms=10_000, wait_ms=0),))
        thread = threading.Thread(target=lambda: runner.run(script, start_delay=0))
        thread.start()
        for _ in range(100):
            if mouse.actions:
                break
            threading.Event().wait(0.01)
        runner.stop()
        thread.join(timeout=1)
        self.assertFalse(thread.is_alive())
        self.assertEqual(mouse.actions, [("press", (1, 2), "L"), ("release", (1, 2), "L")])


if __name__ == "__main__":
    unittest.main()
