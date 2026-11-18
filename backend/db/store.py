"""Append-only SQLite event log (owner: P3). This is also the source for incident replay."""
from __future__ import annotations

import json
import sqlite3
import threading


class EventStore:
    def __init__(self, path: str = ":memory:") -> None:
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._lock = threading.Lock()
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS events ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, t REAL NOT NULL, kind TEXT NOT NULL, payload TEXT NOT NULL)"
        )
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_events_t ON events(t)")
        self._conn.commit()

    def append(self, kind: str, t: float, payload: dict) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO events (t, kind, payload) VALUES (?, ?, ?)", (t, kind, json.dumps(payload))
            )
            self._conn.commit()

    def query(self, t_from: float = 0.0, t_to: float = float("inf"), kind: str | None = None) -> list[dict]:
        sql = "SELECT t, kind, payload FROM events WHERE t >= ? AND t <= ?"
        args: list = [t_from, t_to if t_to != float("inf") else 1e18]
        if kind:
            sql += " AND kind = ?"
            args.append(kind)
        sql += " ORDER BY id"
        with self._lock:
            rows = self._conn.execute(sql, args).fetchall()
        return [{"t": t, "kind": k, "data": json.loads(p)} for t, k, p in rows]
