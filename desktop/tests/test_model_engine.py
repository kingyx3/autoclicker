import tempfile
import threading
import time
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
        script = Script("example", 2, (Step(150, 200, hold_ms=0, wait_ms=1), Step(-50, 10, button="right")),
                        loop=False, time_limit_seconds=120)
        with tempfile.TemporaryDirectory() as folder:
            store = ScriptStore(Path(folder) / "scripts.json")
            store.write([script])
            self.assertEqual(store.load(), [script])
            self.assertEqual(script.to_dict()["steps"][0]["holdMs"], 0)
            self.assertFalse(store.load()[0].loop)
            self.assertEqual(store.load()[0].time_limit_seconds, 120)
            legacy = script.to_dict()
            legacy.pop("loop")
            legacy.pop("timeLimitSeconds")
            self.assertTrue(Script.from_dict(legacy).loop)
            self.assertEqual(Script.from_dict(legacy).time_limit_seconds, 0)

    def test_rejects_invalid_script(self):
        with self.assertRaises(ValueError):
            Script("empty", 1, ())
        with self.assertRaises(ValueError):
            Step(1, 2, hold_ms=-1)

    def test_runs_in_order_and_counts_repetitions(self):
        mouse = FakeMouse()
        runner = Runner(mouse, {"left": "L", "right": "R"})
        script = Script("two points", 2, (Step(1, 2, wait_ms=0), Step(3, 4, wait_ms=0, button="right")), loop=False)
        self.assertEqual(runner.run(script, start_delay=0), 4)
        self.assertEqual(mouse.actions, [
            ("click", (1, 2), "L"), ("click", (3, 4), "R"),
            ("click", (1, 2), "L"), ("click", (3, 4), "R"),
        ])

    def test_reports_first_crosshair_and_keeps_click_order(self):
        mouse = FakeMouse()
        runner = Runner(mouse, {"left": "L"})
        script = Script("markers", 1, (Step(5, 6, wait_ms=60), Step(7, 8, wait_ms=0)), loop=False)
        selected = []
        self.assertEqual(runner.run(script, start_delay=0, step_changed=selected.append), 2)
        self.assertEqual(selected, [0, 1])

    def test_stop_releases_held_button(self):
        mouse = FakeMouse()
        runner = Runner(mouse, {"left": "L"})
        script = Script("hold", 10, (Step(1, 2, hold_ms=10_000, wait_ms=0),), loop=False)
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

    def test_default_loop_wraps_to_first_step_until_stopped(self):
        mouse = FakeMouse()
        runner = Runner(mouse, {"left": "L"})
        script = Script("loop", 1, (Step(1, 2, wait_ms=0), Step(3, 4, wait_ms=0)))
        clicks = []

        def progress(done, total):
            clicks.append((done, total))
            if done == 50:
                runner.stop()

        self.assertEqual(runner.run(script, start_delay=0, progress=progress), 50)
        self.assertEqual([action[1] for action in mouse.actions[:4]],
                         [(1, 2), (3, 4), (1, 2), (3, 4)])
        self.assertEqual(clicks[-1], (50, None))
        self.assertEqual(runner.outcome, "stopped")

    def test_pause_releases_held_button_and_freezes_elapsed(self):
        mouse = FakeMouse()
        runner = Runner(mouse, {"left": "L"})
        script = Script("hold", 1, (Step(1, 2, hold_ms=150, wait_ms=0),), loop=False)
        thread = threading.Thread(target=lambda: runner.run(script, start_delay=0))
        thread.start()
        for _ in range(100):
            if mouse.actions:
                break
            threading.Event().wait(0.005)
        self.assertEqual(mouse.actions[0][0], "press")
        runner.pause()
        for _ in range(100):
            if len(mouse.actions) >= 2:
                break
            threading.Event().wait(0.005)
        self.assertEqual(mouse.actions[1][0], "release")
        elapsed = runner.elapsed()
        threading.Event().wait(0.08)
        self.assertAlmostEqual(runner.elapsed(), elapsed, delta=0.02)
        runner.resume()
        thread.join(timeout=1)
        self.assertFalse(thread.is_alive())
        self.assertEqual([action[0] for action in mouse.actions],
                         ["press", "release", "press", "release"])
        self.assertEqual(runner.outcome, "completed")

    def test_timer_ends_continuous_loop(self):
        mouse = FakeMouse()
        runner = Runner(mouse, {"left": "L"})
        script = Script("timed", 1, (Step(1, 2, wait_ms=100),), time_limit_seconds=1)
        began = time.monotonic()
        self.assertGreater(runner.run(script, start_delay=0), 0)
        self.assertEqual(runner.outcome, "timer")
        self.assertGreaterEqual(time.monotonic() - began, 0.95)
        frozen = runner.elapsed()
        threading.Event().wait(0.03)
        self.assertAlmostEqual(runner.elapsed(), frozen, delta=0.005)

    def test_stop_while_paused_during_countdown(self):
        mouse = FakeMouse()
        runner = Runner(mouse, {"left": "L"})
        script = Script("countdown", 1, (Step(1, 2),))
        countdown_seen = threading.Event()
        result = []

        def countdown(remaining):
            if remaining == 2:
                countdown_seen.set()

        thread = threading.Thread(target=lambda: result.append(
            runner.run(script, start_delay=2, countdown=countdown)))
        thread.start()
        self.assertTrue(countdown_seen.wait(1.5))
        runner.pause()
        frozen = runner.elapsed()
        threading.Event().wait(0.08)
        self.assertEqual(runner.elapsed(), frozen)
        runner.stop()
        thread.join(timeout=1)
        self.assertFalse(thread.is_alive())
        self.assertEqual(result, [0])
        self.assertEqual(runner.outcome, "stopped")
        self.assertEqual(mouse.actions, [])


if __name__ == "__main__":
    unittest.main()
