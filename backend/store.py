"""SQLite store: projects, task board, artifacts, events, clients, decisions, agent metrics."""
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
CREATE TABLE IF NOT EXISTS clients (
  id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE COLLATE NOCASE, contact TEXT DEFAULT '',
  created_at REAL
);
CREATE TABLE IF NOT EXISTS decisions (
  id INTEGER PRIMARY KEY AUTOINCREMENT, client_id INTEGER, project_id TEXT, kind TEXT, text TEXT, at REAL
);
CREATE TABLE IF NOT EXISTS metrics (
  project_id TEXT, agent TEXT, name TEXT, value REAL, at REAL
);
CREATE INDEX IF NOT EXISTS metrics_agent ON metrics(agent, name);
"""

# Decision kinds that are remembered about a client.
DECISION_KINDS = ("choice", "revision", "approved", "changes_requested", "note",
                  "budget", "stopped", "deployed", "sent", "pushed")


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        with self.lock:
            self.db.executescript(SCHEMA)
            cols = {r[1] for r in self.db.execute("PRAGMA table_info(projects)")}
            if "client_id" not in cols:  # migrate databases created before phase 4
                self.db.execute("ALTER TABLE projects ADD COLUMN client_id INTEGER")
            self.db.commit()

    def _x(self, sql: str, args: tuple = ()) -> list[sqlite3.Row]:
        with self.lock:
            cur = self.db.execute(sql, args)
            self.db.commit()
            return cur.fetchall()

    # -- projects
    def create(self, message: str, budget_usd: float, client_id: int | None = None) -> str:
        pid = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
        now = time.time()
        title = message.strip().splitlines()[0][:80]
        self._x("INSERT INTO projects (id, title, message, status, budget_usd, cost, created_at, updated_at,"
                " client_id) VALUES (?,?,?,?,?,?,?,?,?)",
                (pid, title, message, "running", budget_usd, "{}", now, now, client_id))
        for stage, label in STAGES:
            self._x("INSERT INTO tasks VALUES (?,?,?,?,?,?)", (pid, stage, label, "pending", "", now))
        return pid

    def list(self) -> list[dict]:
        rows = self._x("SELECT p.id, p.title, p.status, p.created_at, c.name AS client FROM projects p"
                       " LEFT JOIN clients c ON c.id = p.client_id ORDER BY p.created_at DESC")
        return [dict(r) for r in rows]

    def get(self, pid: str) -> dict | None:
        rows = self._x("SELECT * FROM projects WHERE id=?", (pid,))
        if not rows:
            return None
        p = dict(rows[0])
        p["cost"] = json.loads(p["cost"] or "{}")
        p["client"] = self.get_client(p["client_id"]) if p.get("client_id") else None
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

    def set_cost(self, pid: str, cost: dict) -> None:
        self._x("UPDATE projects SET cost=?, updated_at=? WHERE id=?", (json.dumps(cost), time.time(), pid))

    def set_budget(self, pid: str, budget_usd: float) -> None:
        self._x("UPDATE projects SET budget_usd=?, updated_at=? WHERE id=?", (budget_usd, time.time(), pid))

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

    # -- clients and remembered decisions
    def find_or_create_client(self, name: str) -> int:
        name = " ".join(name.split())[:80] or "Khách lẻ"
        with self.lock:
            row = self.db.execute("SELECT id FROM clients WHERE name=?", (name,)).fetchone()
            if row:
                return row["id"]
            cur = self.db.execute("INSERT INTO clients (name, created_at) VALUES (?,?)", (name, time.time()))
            self.db.commit()
            return cur.lastrowid

    def get_client(self, cid: int) -> dict | None:
        rows = self._x("SELECT id, name, contact, created_at FROM clients WHERE id=?", (cid,))
        return dict(rows[0]) if rows else None

    def update_client(self, cid: int, contact: str) -> None:
        self._x("UPDATE clients SET contact=? WHERE id=?", (contact, cid))

    def clients(self) -> list[dict]:
        rows = self._x("""SELECT c.id, c.name, c.contact, c.created_at, COUNT(p.id) AS projects,
                          MAX(p.created_at) AS last_project_at
                          FROM clients c LEFT JOIN projects p ON p.client_id = c.id
                          GROUP BY c.id ORDER BY last_project_at DESC""")
        return [dict(r) for r in rows]

    def project_client_id(self, pid: str) -> int | None:
        rows = self._x("SELECT client_id FROM projects WHERE id=?", (pid,))
        return rows[0]["client_id"] if rows else None

    def remember(self, pid: str | None, kind: str, text: str, client_id: int | None = None) -> None:
        if kind not in DECISION_KINDS:
            raise ValueError(kind)
        cid = client_id if client_id is not None else (self.project_client_id(pid) if pid else None)
        if cid is None:
            return
        self._x("INSERT INTO decisions (client_id, project_id, kind, text, at) VALUES (?,?,?,?,?)",
                (cid, pid, kind, text, time.time()))

    def decisions(self, cid: int) -> list[dict]:
        rows = self._x("SELECT project_id, kind, text, at FROM decisions WHERE client_id=? ORDER BY id", (cid,))
        return [dict(r) for r in rows]

    def client_memory(self, cid: int, exclude_project: str | None = None) -> dict:
        """What the team knows about a client from earlier projects (input to ai.artifacts.ClientMemory)."""
        client = self.get_client(cid) or {"name": "Khách lẻ", "contact": ""}
        past = []
        for r in self._x("SELECT id, title, status, created_at FROM projects WHERE client_id=? AND id IS NOT ?"
                         " ORDER BY created_at", (cid, exclude_project)):
            brief = self.load(r["id"], "brief") or {}
            proposal = self.load(r["id"], "proposal") or {}
            choice = (self.load(r["id"], "choice") or {}).get("option_id")
            option = next((o for o in proposal.get("options", []) if o["id"] == choice), None)
            past.append({
                "project_id": r["id"], "title": r["title"], "status": r["status"],
                "date": time.strftime("%Y-%m-%d", time.localtime(r["created_at"])),
                "budget": brief.get("budget", "chưa rõ"),
                "chosen_tier": option["tier"] if option else None,
                "chosen_name": option["name"] if option else None,
                "price_vnd": option["est_price_vnd"] if option else None,
                "features": option["features"] if option else [],
            })
        decisions = [d for d in self.decisions(cid) if d["project_id"] != exclude_project or d["kind"] == "note"]
        return {"client_name": client["name"], "contact": client.get("contact", ""), "projects": past,
                "decisions": [{"kind": d["kind"], "text": d["text"],
                               "date": time.strftime("%Y-%m-%d", time.localtime(d["at"]))} for d in decisions]}

    # -- agent quality metrics
    def metric(self, pid: str, agent: str, name: str, value: float) -> None:
        self._x("INSERT INTO metrics VALUES (?,?,?,?,?)", (pid, agent, name, float(value), time.time()))

    def scorecard(self) -> dict[str, dict]:
        """Per-agent quality numbers aggregated over all projects."""
        out: dict[str, dict] = {}
        for r in self._x("""SELECT agent, name, COUNT(*) AS n, AVG(value) AS avg, SUM(value) AS total
                            FROM metrics GROUP BY agent, name"""):
            out.setdefault(r["agent"], {})[r["name"]] = {"n": r["n"], "avg": r["avg"], "total": r["total"]}
        done = self._x("SELECT stage, COUNT(*) AS n FROM tasks WHERE status='done' GROUP BY stage")
        failed = self._x("SELECT stage, COUNT(*) AS n FROM tasks WHERE status IN ('failed','blocked') "
                         "AND stage != 'choice' GROUP BY stage")
        for r in done:
            out.setdefault(r["stage"], {})["tasks_done"] = r["n"]
        for r in failed:
            out.setdefault(r["stage"], {})["tasks_stuck"] = r["n"]
        return out
