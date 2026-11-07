import os
import time

import pytest

os.environ["VTD_LLM"] = "mock"

from ai import agents  # noqa: E402
from ai.artifacts import CodeArtifact, FileOut  # noqa: E402
from ai.llm import BudgetExceeded, CostTracker, MockLLM  # noqa: E402
from ai.orchestrator import run_project  # noqa: E402
from ai.workspace import PermissionDenied, Workspace  # noqa: E402


class MemSink:
    def __init__(self):
        self.tasks, self.artifacts, self.events, self.status = {}, {}, [], None

    def task(self, pid, stage, status, note=""):
        self.tasks[stage] = status

    def artifact(self, pid, name, data):
        self.artifacts[name] = data

    def event(self, pid, text):
        self.events.append(text)

    def finish(self, pid, status, cost):
        self.status = status


MSG = "Làm landing page cho quán cà phê 'Mộc Coffee' ở Đà Lạt, ngân sách 5 triệu, cần trong 1 tuần"


def test_end_to_end_mock(tmp_path):
    sink = MemSink()
    status = run_project("p1", MSG, sink, tmp_path)
    assert status == "awaiting_approval"
    assert all(s == "done" for s in sink.tasks.values()), sink.tasks
    assert sink.artifacts["brief"]["project_name"] == "Mộc Coffee"
    assert sink.artifacts["brief"]["budget"] == "5 triệu"
    assert sink.artifacts["qa"]["passed"]
    assert (tmp_path / "p1" / "index.html").exists()
    assert sink.artifacts["git"]["log"], "dev output should be committed"
    assert "Duyệt deploy lên hosting" in sink.artifacts["report"]["decisions_needed"]


def test_qa_catches_broken_page(tmp_path):
    spec = agents.analyst(MockLLM(CostTracker(1)), agents.intake(MockLLM(CostTracker(1)), MSG))
    ws = Workspace(tmp_path, "p2")
    ws.for_role("frontend_dev").write(
        "index.html",
        '<html><head><script src="https://cdn.example.com/x.js"></script></head>'
        '<body><h1>a</h1><h1>b</h1><img src="a.png"><a href="#nope">x</a></body></html>')
    report = agents.qa(spec, ws.for_role("qa"))
    failed = {c.name for c in report.failures()}
    assert not report.passed
    for name in ["Có <!DOCTYPE html>", "Đúng một thẻ h1", "Ảnh có alt", "Liên kết nội bộ không gãy",
                 "Không phụ thuộc tài nguyên ngoài", "Đủ các section theo spec", "Có nút CTA đúng chữ"]:
        assert name in failed


def test_qa_cannot_write(tmp_path):
    ws = Workspace(tmp_path, "p3")
    with pytest.raises(PermissionDenied):
        ws.for_role("qa").write("index.html", "x")
    with pytest.raises(PermissionDenied):
        ws.for_role("frontend_dev").write("../escape.html", "x")


def test_fix_loop_then_escalate(tmp_path, monkeypatch):
    """A dev that never fixes the bug is stopped after MAX_FIX_ROUNDS and escalated."""
    calls = []

    def bad_dev(llm, spec, ws, failures=None, previous=None):
        calls.append(failures)
        art = CodeArtifact(files=[FileOut(path="index.html", content="<p>broken</p>")], notes="")
        ws.write("index.html", art.files[0].content + str(len(calls)))
        return art

    monkeypatch.setattr(agents, "frontend_dev", bad_dev)
    sink = MemSink()
    status = run_project("p4", MSG, sink, tmp_path)
    assert status == "needs_review"
    assert sink.tasks["qa"] == "blocked"
    assert len(calls) == 3  # first try + 2 fix rounds
    assert calls[1], "QA failures must be handed back to the dev"


def test_budget_cap_stops_run(tmp_path):
    sink = MemSink()
    status = run_project("p5", MSG, sink, tmp_path, budget_usd=1e-9,
                         llm_factory=lambda c: _Spender(c))
    assert status == "over_budget"


class _Spender(MockLLM):
    def structured(self, agent, system, user, schema):
        self.cost.check()
        self.cost.add(agent, "claude-opus-5-5", 1000, 1000)
        return None


def test_api_flow(tmp_path, monkeypatch):
    monkeypatch.setenv("VTD_WORKSPACE", str(tmp_path / "ws"))
    monkeypatch.setenv("VTD_DB", str(tmp_path / "db.sqlite3"))
    import importlib

    import backend.app as appmod
    importlib.reload(appmod)
    from fastapi.testclient import TestClient

    c = TestClient(appmod.app)
    pid = c.post("/api/projects", json={"message": MSG}).json()["id"]
    for _ in range(50):
        p = c.get(f"/api/projects/{pid}").json()
        if p["status"] != "running":
            break
        time.sleep(0.1)
    assert p["status"] == "awaiting_approval"
    assert c.get(f"/preview/{pid}/index.html").status_code == 200
    assert c.get(f"/preview/{pid}/.git/config").status_code == 404
    assert c.post(f"/api/projects/{pid}/decision", json={"approve": True}).json()["status"] == "approved"
    assert c.get("/").status_code == 200
