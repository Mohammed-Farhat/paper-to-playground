"""Execution trace: one JSON object per line in out/trace.jsonl.

Every event records a stage, an action and a result, plus the elapsed seconds
since process start. Events are flushed immediately so a partial trace survives
a crash. Credentials and model reasoning are never written here.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


class Trace:
    def __init__(self, path: Path, t0: float):
        self.path = path
        self.t0 = t0
        self.events: list[dict[str, Any]] = []
        self._fh = path.open("w", encoding="utf-8")

    def elapsed(self) -> float:
        return round(time.monotonic() - self.t0, 3)

    def log(self, stage: str, action: str, result: str, **fields: Any) -> dict[str, Any]:
        event = {"t": self.elapsed(), "stage": stage, "action": action, "result": result}
        event.update(fields)
        self.events.append(event)
        self._fh.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")
        self._fh.flush()
        return event

    def close(self) -> None:
        if not self._fh.closed:
            self._fh.close()
