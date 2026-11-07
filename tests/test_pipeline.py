import os
import time

import pytest

os.environ["VTD_LLM"] = "mock"

from ai import agents  # noqa: E402
from ai.artifacts import CodeArtifact, FileOut  # noqa: E402
from ai.llm import BudgetExceeded, CostTracker, MockLLM  # noqa: E402
from ai.orchestrator import build_project, plan_project, revise_options, run_project  # noqa: E402
from ai.workspace import PermissionDenied, Workspace  # noqa: E402


class MemSink:
    def __init__(self):
        self.tasks, self.artifacts, self.events, self.status = {}, {}, [], None

    def task(self, pid, stage, status, note=""):
        self.tasks[stage] = status

    def artifact(self, pid, name, data):
        self.artifacts[name] = data

    def load(self, pid, name):
        return self.artifacts.get(name)

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
    assert sink.artifacts["choice"]["option_id"] == "B"  # 5 triệu budget -> balanced
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

    def bad_dev(llm, spec, ws, failures=None, previous=None, design=None):
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
    def wait():
        for _ in range(50):
            p = c.get(f"/api/projects/{pid}").json()
            if p["status"] != "running":
                return p
            time.sleep(0.1)

    pid = c.post("/api/projects", json={"message": MSG}).json()["id"]
    p = wait()
    assert p["status"] == "awaiting_choice"
    assert [o["id"] for o in p["artifacts"]["proposal"]["options"]] == ["A", "B", "C"]
    assert c.post(f"/api/projects/{pid}/decision", json={"approve": True}).status_code == 409
    assert c.post(f"/api/projects/{pid}/choice", json={"option_id": "Z"}).status_code == 400
    assert c.post(f"/api/projects/{pid}/choice", json={"note": "rẻ hơn"}).json()["action"] == "revise"
    p = wait()
    assert p["status"] == "awaiting_choice" and p["artifacts"]["revisions"]["notes"] == ["rẻ hơn"]
    assert c.post(f"/api/projects/{pid}/choice", json={"option_id": "C"}).json()["action"] == "build"
    assert c.post(f"/api/projects/{pid}/choice", json={"option_id": "C"}).status_code == 409
    p = wait()
    assert p["status"] == "awaiting_approval", p["events"][-5:]
    assert p["artifacts"]["qa"]["passed"]
    assert c.get(f"/preview/{pid}/index.html").status_code == 200
    assert c.get(f"/preview/{pid}/.git/config").status_code == 404
    assert c.post(f"/api/projects/{pid}/decision", json={"approve": True}).json()["status"] == "approved"
    assert c.get("/").status_code == 200


def test_proposal_options(tmp_path):
    sink = MemSink()
    assert plan_project("p6", MSG, sink) == "awaiting_choice"
    assert sink.tasks["choice"] == "blocked"
    assert "frontend_dev" not in sink.tasks, "nothing is built before the boss chooses"
    opts = sink.artifacts["proposal"]["options"]
    assert [o["tier"] for o in opts] == ["fast", "balanced", "premium"]
    prices = [o["est_price_vnd"] for o in opts]
    assert prices == sorted(prices)
    assert any("Vượt ngân sách" in c for c in opts[2]["cons"])
    for o in opts:
        ids = [s["id"] for s in o["sections"]]
        assert ids[0] == "hero" and "contact" in ids


@pytest.mark.parametrize("option_id", ["A", "B", "C"])
def test_every_option_builds_and_passes_qa(tmp_path, option_id):
    sink = MemSink()
    plan_project("p7", MSG, sink)
    assert build_project("p7", option_id, sink, tmp_path) == "awaiting_approval"
    qa_names = [c["name"] for c in sink.artifacts["qa"]["checks"]]
    option = next(o for o in sink.artifacts["proposal"]["options"] if o["id"] == option_id)
    assert sum(n.startswith("Tính năng:") for n in qa_names) == len(option["features"])
    assert sink.artifacts["qa"]["passed"], [c for c in sink.artifacts["qa"]["checks"] if not c["passed"]]


def test_qa_checks_option_features(tmp_path):
    sink = MemSink()
    plan_project("p8", MSG, sink)
    build_project("p8", "A", sink, tmp_path)  # A has no dark mode / FAQ / form
    from ai.artifacts import Spec
    spec = Spec(**sink.artifacts["final_spec"])
    spec.features = ["dark_mode", "contact_form", "seo_meta"]
    report = agents.qa(spec, Workspace(tmp_path, "p8").for_role("qa"))
    failed = {c.name for c in report.failures()}
    assert len(failed) == 3 and all(n.startswith("Tính năng:") for n in failed)


def test_revision_limit(tmp_path, monkeypatch):
    import ai.orchestrator as orch
    monkeypatch.setattr(orch, "MAX_REVISIONS", 1)
    sink = MemSink()
    plan_project("p9", MSG, sink)
    assert revise_options("p9", "bỏ mục khách hàng", sink) == "awaiting_choice"
    assert "bỏ mục khách hàng" in sink.artifacts["proposal"]["reasoning"]
    revise_options("p9", "lần nữa", sink)
    assert sink.artifacts["revisions"]["notes"] == ["bỏ mục khách hàng"]


def test_cost_carries_across_halves(tmp_path):
    sink = MemSink()
    plan_project("p10", MSG, sink, llm_factory=lambda c: _Spender(c))
    first = sink.artifacts["cost"]["calls"]
    build_project("p10", "A", sink, tmp_path, llm_factory=lambda c: _Spender(c))
    assert sink.artifacts["cost"]["calls"] > first


# ---------------------------------------------------------------- phase 3

from ai import team  # noqa: E402
from ai.artifacts import Spec  # noqa: E402


def _built(tmp_path, option_id, pid):
    sink = MemSink()
    plan_project(pid, MSG, sink)
    status = build_project(pid, option_id, sink, tmp_path)
    return sink, status


def test_premium_has_backend_tested_for_real(tmp_path):
    sink, status = _built(tmp_path, "C", "p11")
    assert status == "awaiting_approval"
    spec = sink.artifacts["final_spec"]
    assert [e["path"] for e in spec["api"]] == ["/api/contact"]
    names = [c["name"] for c in sink.artifacts["qa"]["checks"] if c["owner"] == "backend_dev"]
    assert any(n.startswith("Test backend chạy và đạt (7 test)") for n in names), names
    assert "POST /api/contact nhận dữ liệu hợp lệ" in names
    assert "Không lộ mã nguồn backend qua HTTP" in names
    assert "Form khớp API contract" in [c["name"] for c in sink.artifacts["qa"]["checks"]]
    assert (tmp_path / "p11" / "design" / "design.json").exists()
    assert sink.tasks["designer"] == "done" and sink.tasks["reviewer"] == "done"


def test_static_option_skips_backend(tmp_path):
    sink, status = _built(tmp_path, "B", "p12")
    assert status == "awaiting_approval"
    assert not sink.artifacts["final_spec"]["api"]
    assert not (tmp_path / "p12" / "api").exists()


def test_role_write_scopes(tmp_path):
    ws = Workspace(tmp_path, "p13")
    with pytest.raises(PermissionDenied):
        ws.for_role("frontend_dev").write("api/server.py", "x")
    with pytest.raises(PermissionDenied):
        ws.for_role("backend_dev").write("index.html", "x")
    with pytest.raises(PermissionDenied):
        ws.for_role("designer").write("styles.css", "x")
    with pytest.raises(PermissionDenied):
        ws.for_role("reviewer").write("design/x.json", "x")
    ws.for_role("backend_dev").write("api/server.py", "x")
    ws.for_role("designer").write("design/design.json", "{}")


def test_reviewer_flags_planted_problems(tmp_path):
    ws = Workspace(tmp_path, "p14")
    ws.for_role("backend_dev").write("api/server.py", 'API_KEY = "sk-abcdefghijklmnopqrstuvwxyz"\nexec(body)\n')
    ws.for_role("frontend_dev").write("index.html", '<a href="javascript:alert(1)" onclick="x()">x</a>')
    spec = Spec(project_name="x", page_title="x", goal="x", audience="x", language="vi", sections=[],
                cta_text="x", palette=[], tech="x", acceptance_criteria=[])
    review = team.reviewer(MockLLM(CostTracker(1)), spec, ws.for_role("reviewer"))
    rules = {(f.rule, f.owner) for f in review.findings}
    assert {("hardcoded-secret", "backend_dev"), ("no-eval", "backend_dev"),
            ("javascript-url", "frontend_dev"), ("inline-handler", "frontend_dev")} <= rules
    assert not review.passed


def test_backend_failures_go_to_backend_dev_only(tmp_path, monkeypatch):
    real_backend = team.backend_dev
    front_calls, back_calls = [], []

    def broken_backend(llm, spec, ws, failures=None, previous=None):
        back_calls.append(failures)
        out = real_backend(llm, spec, ws, failures, previous)
        if not failures:  # first version leaks the API source and has no input limits
            ws.write("api/server.py", ws.read("api/server.py").replace('parts[0] in ("api", ".git", ".vtd")', "False"))
        return out

    real_front = agents.frontend_dev

    def counting_front(*a, **k):
        front_calls.append(1)
        return real_front(*a, **k)

    monkeypatch.setattr(team, "backend_dev", broken_backend)
    monkeypatch.setattr(agents, "frontend_dev", counting_front)
    sink, status = _built(tmp_path, "C", "p15")
    assert status == "awaiting_approval"
    assert len(back_calls) == 2 and back_calls[1], "backend got its failures back"
    assert len(front_calls) == 1, "frontend was not re-run for a backend bug"


def test_designer_enforces_contrast(tmp_path):
    from ai.artifacts import DesignSpec, SectionDesign

    class BadDesigner(MockLLM):
        def structured(self, agent, system, user, schema):
            return DesignSpec(colors={"surface": "#ffffff", "ink": "#eeeeee"}, font_stack="x", radius_px=4,
                              max_width_px=900, sections=[SectionDesign(id="hero", layout="grid")], notes=[])

    spec = agents.analyst(MockLLM(CostTracker(1)), agents.intake(MockLLM(CostTracker(1)), MSG))
    d = team.designer(BadDesigner(CostTracker(1)), spec, Workspace(tmp_path, "p16").for_role("designer"))
    assert team.contrast(d.colors["ink"], d.colors["surface"]) >= 4.5
    assert [s.id for s in d.sections] == [s.id for s in spec.sections]
    assert d.sections[0].layout == "hero"


def test_websocket_office_feed(tmp_path, monkeypatch):
    monkeypatch.setenv("VTD_WORKSPACE", str(tmp_path / "ws"))
    monkeypatch.setenv("VTD_DB", str(tmp_path / "db.sqlite3"))
    import importlib

    import backend.app as appmod
    importlib.reload(appmod)
    from fastapi.testclient import TestClient

    c = TestClient(appmod.app)
    with c.websocket_connect("/ws/events") as ws:
        snap = ws.receive_json()
        assert snap["type"] == "snapshot" and snap["company"]
        assert {a["group"] for a in snap["agents"]} == {"lead", "code", "creative"}
        assert all(a["status"] == "idle" for a in snap["agents"])
        ws.send_json({"type": "assign", "to": "leader", "text": MSG})
        seen = []
        while True:
            msg = ws.receive_json()
            seen.append(msg)
            if msg["type"] == "task" and msg["task"]["status"] == "review":
                break
        kinds = {m["type"] for m in seen}
        assert {"log", "agent", "task"} <= kinds
        assert seen[0] == {"type": "log", "entry": seen[0]["entry"]} and seen[0]["entry"]["kind"] == "assign"
        task = seen[-1]["task"]
        assert task["id"].startswith("TD-") and task["assignee"] == "leader"
        assert set(task) >= {"id", "title", "description", "assigner", "assignee", "status", "files",
                             "createdAt", "updatedAt"}
        working = [m["agent"] for m in seen if m["type"] == "agent" and m["agent"].get("status") == "working"]
        assert {"intake", "architect"} <= {a["id"] for a in working}
        assert all(a["status"] in ("idle", "working", "blocked") for m in seen if m["type"] == "agent"
                   for a in [m["agent"]] if "status" in a)

    pid = c.get("/api/projects").json()[0]["id"]
    assert c.post(f"/api/projects/{pid}/choice", json={"option_id": "C"}).status_code == 200
    for _ in range(100):
        if c.get(f"/api/projects/{pid}").json()["status"] != "running":
            break
        time.sleep(0.1)
    with c.websocket_connect("/ws/events") as ws:
        snap = ws.receive_json()
        tasks = {t["assignee"]: t for t in snap["tasks"]}
        assert tasks["backend"]["status"] == "done" and tasks["backend"]["files"]
        assert tasks["reviewer"]["status"] == "done"


def test_qa_does_not_touch_project_data(tmp_path):
    _built(tmp_path, "C", "p17")
    assert not (tmp_path / "p17" / "api" / "data").exists()
