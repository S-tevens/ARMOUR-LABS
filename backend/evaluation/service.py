"""Runs the evaluation in the background and serves the latest results (owner: P3)."""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from detect.bundle import peek_bundle
from evaluation.run import RESULTS, full_evaluation


class EvaluationService:
    def __init__(self, path: Path = RESULTS) -> None:
        self.path = path
        self._lock = threading.Lock()
        self._running = False
        self._progress = ""
        self._started = 0.0
        self._error: str | None = None

    def live(self) -> dict:
        b = peek_bundle()
        return {"ready": b is not None, "selected_model": b.selected if b else None,
                "model": b.ml.label if b else None}

    def status(self) -> dict:
        """The latest results, or a status the page can show while there are none or a run is in progress."""
        base = {"live_detector": self.live()}
        if self._running:
            return {**base, "status": "running", "progress": self._progress, "elapsed_s": round(time.time() - self._started)}
        if self._error:
            return {**base, "status": "error", "error": self._error}
        if self.path.exists():
            return {**base, **json.loads(self.path.read_text(encoding="utf-8")), "status": "ok"}
        return {**base, "status": "not_computed",
                "note": "No evaluation has been run yet. Press Run evaluation, or run: python -m evaluation.run"}

    def start(self) -> bool:
        with self._lock:
            if self._running:
                return False
            self._running, self._error, self._started, self._progress = True, None, time.time(), "starting"
        threading.Thread(target=self._work, daemon=True, name="evaluation").start()
        return True

    def _work(self) -> None:
        try:
            res = full_evaluation(progress=lambda m: setattr(self, "_progress", m))
            self.path.write_text(json.dumps(res, indent=1), encoding="utf-8")
        except Exception as e:  # reported to the page, never raised into the server
            self._error = f"{type(e).__name__}: {e}"
        finally:
            self._running = False
