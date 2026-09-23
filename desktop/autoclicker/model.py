from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path


def data_path() -> Path:
    if sys.platform == "win32":
        root = Path(os.environ.get("APPDATA", Path.home()))
    elif sys.platform == "darwin":
        root = Path.home() / "Library" / "Application Support"
    else:
        root = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return root / "AutoClicker" / "scripts.json"


@dataclass(frozen=True)
class Step:
    x: int
    y: int
    radius: int = 24
    hold_ms: int = 0
    wait_ms: int = 100
    button: str = "left"

    def __post_init__(self) -> None:
        if type(self.x) is not int or type(self.y) is not int or not (-100_000 <= self.x <= 100_000 and -100_000 <= self.y <= 100_000):
            raise ValueError("Coordinates must be integers within ±100000")
        if type(self.radius) is not int or not 1 <= self.radius <= 200:
            raise ValueError("Marker radius must be 1–200")
        if type(self.hold_ms) is not int or not 0 <= self.hold_ms <= 60_000:
            raise ValueError("Hold must be 0–60000 ms")
        if type(self.wait_ms) is not int or not 0 <= self.wait_ms <= 600_000:
            raise ValueError("Wait must be 0–600000 ms")
        if self.button not in ("left", "right", "middle"):
            raise ValueError("Choose left, right, or middle button")


@dataclass(frozen=True)
class Script:
    name: str
    repetitions: int
    steps: tuple[Step, ...]
    loop: bool = True
    time_limit_seconds: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip() or len(self.name) > 100:
            raise ValueError("Name must contain 1–100 characters")
        if type(self.repetitions) is not int or not 1 <= self.repetitions <= 10_000:
            raise ValueError("Repetitions must be 1–10000")
        if type(self.loop) is not bool:
            raise ValueError("Loop must be enabled or disabled")
        if type(self.time_limit_seconds) is not int or not 0 <= self.time_limit_seconds <= 86_400:
            raise ValueError("Run timer must be 0–86400 seconds")
        if not 1 <= len(self.steps) <= 100 or not all(isinstance(step, Step) for step in self.steps):
            raise ValueError("A script needs 1–100 valid steps")

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "repetitions": self.repetitions,
            "loop": self.loop,
            "timeLimitSeconds": self.time_limit_seconds,
            "steps": [{"x": s.x, "y": s.y, "radius": s.radius, "holdMs": s.hold_ms,
                       "waitMs": s.wait_ms, "button": s.button} for s in self.steps],
        }

    @classmethod
    def from_dict(cls, obj: dict) -> Script:
        return cls(
            name=obj["name"], repetitions=obj["repetitions"],
            loop=obj.get("loop", True), time_limit_seconds=obj.get("timeLimitSeconds", 0),
            steps=tuple(Step(x=s["x"], y=s["y"], radius=s.get("radius", 24),
                             hold_ms=s["holdMs"], wait_ms=s["waitMs"],
                             button=s.get("button", "left")) for s in obj["steps"]),
        )


class ScriptStore:
    def __init__(self, path: Path | None = None):
        self.path = path or data_path()

    def load(self) -> list[Script]:
        if not self.path.exists():
            return []
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError("Script file must contain an array")
        return [Script.from_dict(item) for item in payload]

    def write(self, scripts: list[Script]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        try:
            with temporary.open("w", encoding="utf-8") as stream:
                json.dump([script.to_dict() for script in scripts], stream, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            temporary.unlink(missing_ok=True)
