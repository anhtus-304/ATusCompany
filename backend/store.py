"""SQLite store for projects, the task board, artifacts and events."""
from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from pathlib import Path

from ai.orchestrator import STAGES

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
  id TEXT PRIMARY KEY, title TEXT, message TEXT, status TEXT,
  budget_usd REAL, cost TEXT, created_at REAL, updated_at REAL
);
CREATE TABLE IF NOT EXISTS tasks (
  project_id TEXT, stage TEXT, label TEXT, status TEXT, note TEXT, updated_at REAL,
  PRIMARY KEY (project_id, stage)
);
CREATE TABLE IF NOT EXISTS artifacts (
  project_id TEXT, name TEXT, data TEXT, updated_at REAL, PRIMARY KEY (project_id, name)
);
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT, project_id TEXT, text TEXT, at REAL
);
"""


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        with self.lock:
            self.db.executescript(SCHEMA)

    def _x(self, sql: str, args: tuple = ()) -> list[sqlite3.Row]:
        with self.lock:
            cur = self.db.execute(sql, args)
            self.db.commit()
            return cur.fetchall()

    # -- projects
    def create(self, message: str, budget_usd: float) -> str:
        pid = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
        now = time.time()
        title = message.strip().splitlines()[0][:80]
        self._x("INSERT INTO projects VALUES (?,?,?,?,?,?,?,?)",
                (pid, title, message, "running", budget_usd, "{}", now, now))
        for stage, label in STAGES:
            self._x("INSERT INTO tasks VALUES (?,?,?,?,?,?)", (pid, stage, label, "pending", "", now))
        return pid

    def list(self) -> list[dict]:
        rows = self._x("SELECT id, title, status, created_at FROM projects ORDER BY created_at DESC")
        return [dict(r) for r in rows]

    def get(self, pid: str) -> dict | None:
        rows = self._x("SELECT * FROM projects WHERE id=?", (pid,))
        if not rows:
            return None
        p = dict(rows[0])
        p["cost"] = json.loads(p["cost"] or "{}")
        order = {s: i for i, (s, _) in enumerate(STAGES)}
        tasks = [dict(r) for r in self._x("SELECT stage, label, status, note FROM tasks WHERE project_id=?", (pid,))]
        p["tasks"] = sorted(tasks, key=lambda t: order.get(t["stage"], 99))
        p["artifacts"] = {r["name"]: json.loads(r["data"])
                          for r in self._x("SELECT name, data FROM artifacts WHERE project_id=?", (pid,))}
        p["events"] = [dict(r) for r in self._x(
            "SELECT text, at FROM events WHERE project_id=? ORDER BY id", (pid,))]
        return p

    def get_meta(self, pid: str) -> dict | None:
        rows = self._x("SELECT id, title, status FROM projects WHERE id=?", (pid,))
        return dict(rows[0]) if rows else None

    def task_row(self, pid: str, stage: str) -> dict | None:
        rows = self._x("SELECT rowid, label FROM tasks WHERE project_id=? AND stage=?", (pid, stage))
        return dict(rows[0]) if rows else None

    def set_status(self, pid: str, status: str) -> None:
        self._x("UPDATE projects SET status=?, updated_at=? WHERE id=?", (status, time.time(), pid))

    def transition(self, pid: str, expected: str, status: str) -> bool:
        """Atomically move from one status to another, so a double click can't start two runs."""
        with self.lock:
            cur = self.db.execute("UPDATE projects SET status=?, updated_at=? WHERE id=? AND status=?",
                                  (status, time.time(), pid, expected))
            self.db.commit()
            return cur.rowcount == 1

    # -- Sink protocol used by the orchestrator
    def load(self, pid: str, name: str) -> dict | None:
        rows = self._x("SELECT data FROM artifacts WHERE project_id=? AND name=?", (pid, name))
        return json.loads(rows[0]["data"]) if rows else None

    def task(self, pid: str, stage: str, status: str, note: str = "") -> None:
        self._x("UPDATE tasks SET status=?, note=?, updated_at=? WHERE project_id=? AND stage=?",
                (status, note, time.time(), pid, stage))
        self.event(pid, f"[{stage}] {status}" + (f": {note}" if note else ""))

    def artifact(self, pid: str, name: str, data: dict) -> None:
        self._x("INSERT OR REPLACE INTO artifacts VALUES (?,?,?,?)",
                (pid, name, json.dumps(data, ensure_ascii=False), time.time()))

    def event(self, pid: str, text: str) -> None:
        self._x("INSERT INTO events (project_id, text, at) VALUES (?,?,?)", (pid, text, time.time()))

    def finish(self, pid: str, status: str, cost: dict) -> None:
        self._x("UPDATE projects SET status=?, cost=?, updated_at=? WHERE id=?",
                (status, json.dumps(cost), time.time(), pid))
