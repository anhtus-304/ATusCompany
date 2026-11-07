"""Live "office" view of the agent team, streamed to the pixel dashboard over WebSocket.

The contract matches dashboard/src/types.ts:
  server -> client: snapshot | agent | task | log
  client -> server: {type: "assign", to, text}

The orchestrator reports progress through a Sink. OfficeSink wraps the SQLite
store, so every task change is persisted and also published to the office.
"""
from __future__ import annotations

import asyncio
import itertools
import threading
from collections import deque
from datetime import datetime, timezone

# Agent roster. Stage -> agent and the activity shown while that stage runs.
AGENTS = [
    {"id": "leader", "name": "Trưởng phòng", "role": "PM / Tech Lead", "group": "lead"},
    {"id": "intake", "name": "Lễ tân", "role": "Tiếp nhận yêu cầu", "group": "lead"},
    {"id": "architect", "name": "Kiến trúc sư", "role": "BA / Solution Architect", "group": "lead"},
    {"id": "reporter", "name": "Báo cáo viên", "role": "Báo cáo cho sếp", "group": "lead"},
    {"id": "frontend", "name": "Frontend Dev", "role": "Lập trình giao diện", "group": "code"},
    {"id": "backend", "name": "Backend Dev", "role": "Lập trình API", "group": "code"},
    {"id": "reviewer", "name": "Reviewer", "role": "Soát bảo mật và chất lượng", "group": "code"},
    {"id": "designer", "name": "Designer", "role": "UI/UX Designer", "group": "creative"},
    {"id": "qa", "name": "Tester", "role": "QA, chạy test thật", "group": "creative"},
]

STAGE_AGENT = {
    "intake": ("intake", "reading"),
    "analyst": ("architect", "thinking"),
    "proposer": ("architect", "thinking"),
    "choice": ("leader", "meeting"),
    "designer": ("designer", "drawing"),
    "backend_dev": ("backend", "typing"),
    "frontend_dev": ("frontend", "typing"),
    "qa": ("qa", "testing"),
    "reviewer": ("reviewer", "reviewing"),
    "reporter": ("reporter", "typing"),
}

STAGE_FILES = {
    "designer": ["design/design.json"],
    "backend_dev": ["api/server.py", "api/test_server.py"],
    "frontend_dev": ["index.html", "styles.css"],
}

TASK_STATUS = {"pending": "todo", "running": "doing", "done": "done", "failed": "error", "blocked": "blocked"}
LOG_KIND = {"running": "start", "done": "done", "failed": "error", "blocked": "blocked"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Office:
    def __init__(self, log_size: int = 300):
        self.lock = threading.Lock()
        self.agents = {a["id"]: {**a, "status": "idle", "activity": "idle", "location": "desk",
                                 "taskId": None, "note": "Sẵn sàng", "bubble": None} for a in AGENTS}
        self.tasks: dict[str, dict] = {}
        self.log: deque[dict] = deque(maxlen=log_size)
        self._ids = itertools.count(1)
        self._subs: set[tuple[asyncio.AbstractEventLoop, asyncio.Queue]] = set()
        self.metrics_provider = None  # () -> {agent_id: metrics}; set by the app

    # -- subscribers (one per WebSocket)
    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=1000)
        with self.lock:
            self._subs.add((asyncio.get_running_loop(), q))
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        with self.lock:
            self._subs = {s for s in self._subs if s[1] is not q}

    def _publish(self, msg: dict) -> None:
        for loop, q in list(self._subs):
            try:
                loop.call_soon_threadsafe(self._offer, q, msg)
            except RuntimeError:  # loop closed
                self.unsubscribe(q)

    @staticmethod
    def _offer(q: asyncio.Queue, msg: dict) -> None:
        if q.full():  # slow client: drop oldest rather than block the pipeline
            q.get_nowait()
        q.put_nowait(msg)

    def snapshot(self, company: str) -> dict:
        metrics = self.metrics_provider() if self.metrics_provider else {}
        with self.lock:
            tasks = sorted(self.tasks.values(), key=lambda t: t["createdAt"])[-200:]
            agents = [{**a, "metrics": metrics.get(a["id"])} if a["id"] in metrics else dict(a)
                      for a in self.agents.values()]
            return {"type": "snapshot", "company": company, "agents": agents,
                    "tasks": tasks, "log": list(self.log)}

    # -- state changes
    def add_log(self, agent_id: str | None, kind: str, text: str, task_id: str | None = None) -> None:
        entry = {"id": f"L{next(self._ids)}", "ts": now(), "agentId": agent_id, "taskId": task_id,
                 "kind": kind, "text": text}
        with self.lock:
            self.log.append(entry)
        self._publish({"type": "log", "entry": entry})

    def update_agent(self, agent_id: str, **fields) -> None:
        with self.lock:
            agent = self.agents[agent_id]
            agent.update(fields)
            msg = {"type": "agent", "agent": {"id": agent_id, **fields}}
        self._publish(msg)

    def task_changed(self, task_id: str, project_id: str, project_title: str, stage: str, label: str,
                     status: str, note: str) -> None:
        agent_id, activity = STAGE_AGENT.get(stage, ("leader", "thinking"))
        task_status = "review" if (stage == "choice" and status == "blocked") else TASK_STATUS.get(status, "todo")
        stamp = now()
        with self.lock:
            task = self.tasks.get(task_id) or {
                "id": task_id, "title": f"{label}: {project_title}"[:120], "description": "",
                "assigner": "boss" if stage in ("intake", "choice") else "leader", "assignee": agent_id,
                "status": "todo", "files": [], "screenshot": None, "createdAt": stamp, "updatedAt": stamp,
                "projectId": project_id}
            task.update(status=task_status, updatedAt=stamp, description=note or task["description"])
            if status == "done" and stage in STAGE_FILES:
                task["files"] = [f"workspace/projects/{project_id}/{f}" for f in STAGE_FILES[stage]]
            self.tasks[task_id] = task
            task_msg = {"type": "task", "task": dict(task)}
        self._publish(task_msg)

        if status == "running":
            self.update_agent(agent_id, status="working", activity=activity, taskId=task_id,
                              location="meeting" if activity == "meeting" else "desk",
                              note=f"{label}: {note}" if note else label, bubble=None)
        elif status == "blocked" and stage == "choice":
            self.update_agent(agent_id, status="working", activity="meeting", location="meeting",
                              taskId=task_id, note="Chờ sếp chọn phương án", bubble=f"{task_id} chờ sếp chọn")
        elif status in ("blocked", "failed"):
            self.update_agent(agent_id, status="blocked", activity="idle", location="desk", taskId=task_id,
                              note=note or "Bị chặn", bubble=None)
        elif status == "done":
            self.update_agent(agent_id, status="idle", activity="idle", location="desk", taskId=None,
                              note=f"Xong {task_id}" + (f": {note}" if note else ""), bubble=None)
        if status != "pending":
            kind = "review" if task_status == "review" else LOG_KIND.get(status, "info")
            self.add_log(agent_id, kind, f"{label}" + (f": {note}" if note else ""), task_id)


class OfficeSink:
    """Orchestrator sink that persists to the store and mirrors changes to the office."""

    def __init__(self, store, office: Office):
        self.store, self.office = store, office

    def _title(self, pid: str) -> str:
        p = self.store.get_meta(pid)
        return p["title"] if p else pid

    def task(self, pid: str, stage: str, status: str, note: str = "") -> None:
        self.store.task(pid, stage, status, note)
        row = self.store.task_row(pid, stage)
        if row:
            self.office.task_changed(f"TD-{row['rowid']}", pid, self._title(pid), stage, row["label"], status, note)

    def artifact(self, pid: str, name: str, data: dict) -> None:
        self.store.artifact(pid, name, data)

    def load(self, pid: str, name: str):
        return self.store.load(pid, name)

    def event(self, pid: str, text: str) -> None:
        self.store.event(pid, text)
        if not text.startswith("Traceback"):
            self.office.add_log("leader", "info", text)

    def metric(self, pid: str, agent: str, name: str, value: float) -> None:
        self.store.metric(pid, agent, name, value)

    def finish(self, pid: str, status: str, cost: dict) -> None:
        self.store.finish(pid, status, cost)
        if self.office.metrics_provider:
            for agent_id, m in self.office.metrics_provider().items():
                self.office.update_agent(agent_id, metrics=m)
        labels = {"awaiting_choice": "chờ sếp chọn phương án", "awaiting_approval": "xong, chờ sếp duyệt gửi khách",
                  "needs_review": "cần sếp xử lý", "over_budget": "chạm trần ngân sách", "failed": "gặp lỗi"}
        kind = {"awaiting_approval": "done", "awaiting_choice": "review", "needs_review": "blocked",
                "over_budget": "blocked", "failed": "error"}.get(status, "info")
        self.office.add_log("leader", kind, f"Dự án \"{self._title(pid)[:60]}\" {labels.get(status, status)}"
                            f" (chi phí ${cost.get('spent_usd', 0):.4f})")


def build_scorecard(store) -> dict[str, dict]:
    """Quality per office agent (camelCase, matches the dashboard's optional Agent.metrics)."""
    raw = store.scorecard()
    out: dict[str, dict] = {}
    for stage, data in raw.items():
        agent_id = STAGE_AGENT.get(stage, (None,))[0]
        if not agent_id:
            continue
        a = out.setdefault(agent_id, {"tasksDone": 0, "tasksStuck": 0, "seconds": [0.0, 0], "costUsd": 0.0})
        a["tasksDone"] += data.get("tasks_done", 0)
        a["tasksStuck"] += data.get("tasks_stuck", 0)
        if "seconds" in data:
            a["seconds"][0] += data["seconds"]["total"]
            a["seconds"][1] += data["seconds"]["n"]
        if "cost_usd" in data:
            a["costUsd"] += data["cost_usd"]["total"]
        if "first_pass" in data:
            a["firstPassRate"] = round(data["first_pass"]["avg"], 3)
            a["avgRounds"] = round(data["rounds"]["avg"], 2) if "rounds" in data else None
        if "findings" in data:
            a["findingsPerProject"] = round(data["findings"]["avg"], 2)
            a["blockingPerProject"] = round(data.get("blocking_findings", {}).get("avg", 0), 2)
        if "checks" in data:
            a["checksPerProject"] = round(data["checks"]["avg"], 1)
        if "boss_approved" in data:
            a["approvalRate"] = round(data["boss_approved"]["avg"], 3)
    for a in out.values():
        total, n = a.pop("seconds")
        a["avgSeconds"] = round(total / n, 2) if n else None
        a["costUsd"] = round(a["costUsd"], 6)
    return out
