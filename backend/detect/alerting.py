"""The alert rule shared by every detector (owner: P3).

A detector raises an alert when its score is at or above ALERT_LEVEL for two consecutive ticks. Using the same rule for
all detectors keeps the comparison fair and stops a single noisy tick from opening an incident.
"""
from __future__ import annotations

import numpy as np

ALERT_LEVEL = 0.8
PERSISTENCE = 2  # consecutive ticks


def persist(above: np.ndarray) -> np.ndarray:
    """True where the signal has been above the alert level for PERSISTENCE consecutive ticks."""
    a = np.asarray(above, dtype=bool)
    out = a.copy()
    out[1:] = a[1:] & a[:-1]
    out[0] = False
    return out


def first_alert(alert: np.ndarray, start: int, stop: int) -> int | None:
    """Seconds from `start` to the first alert inside [start, stop), or None if the window passed without one."""
    w = np.asarray(alert[start:stop], dtype=bool)
    return int(np.argmax(w)) if w.any() else None
