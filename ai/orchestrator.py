"""Pipeline, in two halves split by the boss's decision.

plan_project:   message -> brief -> spec -> 3 options        -> pause "awaiting_choice"
revise_options: boss feedback -> new options                  -> pause "awaiting_choice"
build_project:  chosen option -> final spec (+ API contract)
                -> Designer || Backend Dev          (parallel: independent)
                -> Frontend Dev                     (needs design + contract)
                -> QA || Reviewer                   (parallel: both read-only)
                -> failures routed to the owning dev, up to MAX_FIX_ROUNDS
                -> report                           -> pause "awaiting_approval"

The orchestrator owns sequencing and the task board. Agents only see the
artifacts they need. QA and review failures go back to the dev who owns the
file, never straight to the boss; past MAX_FIX_ROUNDS the project is escalated.
"""
from __future__ import annotations

import os
import traceback
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterator, Protocol

from . import agents, team
import time

from .artifacts import Brief, Check, ClientMemory, Proposal, QAReport, Spec
from .llm import BudgetExceeded, CostTracker, LLM, make_llm
from .workspace import Workspace

MAX_FIX_ROUNDS = int(os.environ.get("VTD_MAX_FIX_ROUNDS", "2"))
MAX_REVISIONS = int(os.environ.get("VTD_MAX_REVISIONS", "3"))

STAGES = [
    ("intake", "Lễ tân"),
    ("analyst", "BA / Architect"),
    ("proposer", "Đề xuất phương án"),
    ("choice", "Sếp chọn"),
    ("designer", "UI/UX Designer"),
    ("backend_dev", "Backend Dev"),
    ("frontend_dev", "Frontend Dev"),
    ("qa", "QA"),
    ("reviewer", "Reviewer"),
    ("reporter", "Báo cáo viên"),
]

LLMFactory = Callable[[CostTracker], LLM]


class Sink(Protocol):
    """Where the orchestrator reads and writes project state (backend store, CLI, tests)."""

    def task(self, project_id: str, stage: str, status: str, note: str = "") -> None: ...
    def artifact(self, project_id: str, name: str, data: dict) -> None: ...
    def load(self, project_id: str, name: str) -> dict | None: ...
    def event(self, project_id: str, text: str) -> None: ...
    def finish(self, project_id: str, status: str, cost: dict) -> None: ...
    # Optional: def metric(self, project_id: str, agent: str, name: str, value: float) -> None


def _memory(sink: Sink, pid: str) -> ClientMemory | None:
    data = sink.load(pid, "memory")
    return ClientMemory(**data) if data else None


class _Run:
    """Shared plumbing for one orchestrator call: cost, llm, current stage, error handling."""

    def __init__(self, pid: str, sink: Sink, budget_usd: float, llm_factory: LLMFactory):
        self.pid, self.sink = pid, sink
        saved = sink.load(pid, "cost") or {}
        self.cost = CostTracker.from_dict(saved, budget_usd)
        self.llm = llm_factory(self.cost)
        self.stage = "intake"
        self.status: str | None = None
        self._started: dict[str, float] = {}

    def metric(self, agent: str, name: str, value: float) -> None:
        fn = getattr(self.sink, "metric", None)
        if fn:
            fn(self.pid, agent, name, value)

    def step(self, stage: str, status: str, note: str = "") -> None:
        self.stage = stage
        if status == "running":
            self._started.setdefault(stage, time.monotonic())
        elif status in ("done", "failed", "blocked") and stage in self._started:
            self.metric(stage, "seconds", time.monotonic() - self._started.pop(stage))
        self.sink.task(self.pid, stage, status, note)

    def save(self, name: str, data: dict) -> None:
        self.sink.artifact(self.pid, name, data)

    def end(self, status: str) -> str:
        self.status = status
        before = (self.sink.load(self.pid, "cost") or {}).get("by_agent", {})
        for agent, usd in self.cost.by_agent.items():
            if usd - before.get(agent, 0.0) > 0:
                self.metric(agent, "cost_usd", usd - before.get(agent, 0.0))
        self.save("cost", self.cost.to_dict())
        self.sink.finish(self.pid, status, self.cost.to_dict())
        return status

    @contextmanager
    def guard(self) -> Iterator["_Run"]:
        try:
            yield self
        except BudgetExceeded as e:
            self.step(self.stage, "blocked", str(e))
            self.sink.event(self.pid, f"Dừng vì chạm trần ngân sách: {e}")
            self.end("over_budget")
        except Exception as e:  # noqa: BLE001 - surface any agent failure on the board
            self.step(self.stage, "failed", f"{type(e).__name__}: {e}")
            self.sink.event(self.pid, traceback.format_exc(limit=3))
            self.end("failed")


def _propose(r: _Run, brief: Brief, spec: Spec, note: str = "", previous: Proposal | None = None) -> str:
    r.step("proposer", "running", "chỉnh theo góp ý" if note else "")
    proposal = agents.proposer(r.llm, brief, spec, note, previous, _memory(r.sink, r.pid))
    r.save("proposal", proposal.model_dump())
    r.step("proposer", "done", f"{len(proposal.options)} phương án, khuyên {proposal.recommended}")
    r.step("choice", "blocked", "chờ sếp chọn")
    return r.end("awaiting_choice")


def plan_project(pid: str, message: str, sink: Sink, budget_usd: float = 2.0,
                 llm_factory: LLMFactory = make_llm) -> str:
    r = _Run(pid, sink, budget_usd, llm_factory)
    sink.event(pid, f"Bắt đầu dự án, model: {r.llm.name}, trần ngân sách ${budget_usd:.2f}")
    with r.guard():
        r.step("intake", "running")
        memory = _memory(sink, pid)
        if memory and memory.is_returning:
            sink.event(pid, f"Khách quen {memory.client_name}: {len(memory.projects)} dự án trước, "
                            f"{len(memory.decisions)} quyết định đã chốt")
        brief = agents.intake(r.llm, message, memory)
        r.save("brief", brief.model_dump())
        r.step("intake", "done", f"{len(brief.open_questions)} câu hỏi mở")

        r.step("analyst", "running")
        spec = agents.analyst(r.llm, brief)
        r.save("spec", spec.model_dump())
        r.step("analyst", "done", f"{len(spec.sections)} mục")

        return _propose(r, brief, spec)
    return r.status or "failed"


def revise_options(pid: str, note: str, sink: Sink, budget_usd: float = 2.0,
                   llm_factory: LLMFactory = make_llm) -> str:
    r = _Run(pid, sink, budget_usd, llm_factory)
    revisions = (sink.load(pid, "revisions") or {"notes": []})["notes"]
    with r.guard():
        r.stage = "proposer"
        if len(revisions) >= MAX_REVISIONS:
            sink.event(pid, f"Đã chỉnh {MAX_REVISIONS} lần, cần sếp chọn một phương án hoặc giao việc mới")
            return r.end("awaiting_choice")
        revisions.append(note)
        r.save("revisions", {"notes": revisions})
        sink.event(pid, f"Sếp yêu cầu chỉnh phương án: {note}")
        brief = Brief(**sink.load(pid, "brief"))
        spec = Spec(**sink.load(pid, "spec"))
        previous = Proposal(**sink.load(pid, "proposal"))
        return _propose(r, brief, spec, note, previous)
    return r.status or "failed"


def build_project(pid: str, option_id: str, sink: Sink, workspace_root: Path, budget_usd: float = 2.0,
                  llm_factory: LLMFactory = make_llm) -> str:
    r = _Run(pid, sink, budget_usd, llm_factory)
    with r.guard():
        brief = Brief(**sink.load(pid, "brief"))
        proposal = Proposal(**sink.load(pid, "proposal"))
        option = proposal.get(option_id)
        if option is None:
            raise ValueError(f"Không có phương án {option_id}")
        r.save("choice", {"option_id": option.id})
        r.step("choice", "done", f"{option.id}: {option.name}")

        spec = agents.apply_option(Spec(**sink.load(pid, "spec")), option)
        r.save("final_spec", spec.model_dump())

        ws = Workspace(workspace_root, pid)
        views = {role: ws.for_role(role) for role in ("designer", "frontend_dev", "backend_dev", "qa", "reviewer")}

        # 1. Designer and Backend Dev don't depend on each other: run in parallel.
        def run_designer():
            r.step("designer", "running")
            d = team.designer(r.llm, spec, views["designer"])
            r.save("design", d.model_dump())
            r.step("designer", "done", f"{len(d.sections)} bố cục")
            return d

        def run_backend(failures=None, previous=None):
            if not spec.api:
                return None
            r.step("backend_dev", "running", "sửa lỗi" if failures else ", ".join(e.path for e in spec.api))
            out = team.backend_dev(r.llm, spec, views["backend_dev"], failures, previous)
            r.step("backend_dev", "done", f"{len(out.files)} file")
            return out

        with ThreadPoolExecutor(max_workers=2) as pool:
            fut_design, fut_backend = pool.submit(run_designer), pool.submit(run_backend)
            design, backend_code = fut_design.result(), fut_backend.result()
        if not spec.api:
            r.step("backend_dev", "done", "không cần backend")

        # 2. Frontend needs the design and the API contract.
        front_code, front_fail, back_fail, rounds = None, None, None, 0
        front_rounds, back_rounds = 0, (1 if spec.api else 0)
        need_front = True
        while True:
            if need_front:
                r.step("frontend_dev", "running", f"vòng {rounds + 1}")
                front_code = agents.frontend_dev(r.llm, spec, views["frontend_dev"], front_fail, front_code, design)
                front_rounds += 1
                r.step("frontend_dev", "done")
            if back_fail:
                backend_code = run_backend([f"{c.name}: {c.detail}" for c in back_fail], backend_code)
                back_rounds += 1
            sha = ws.commit(f"option {option.id}, round {rounds + 1}" + (" (fixes)" if rounds else ""))
            sink.event(pid, f"Commit {sha}" if sha else "Không có thay đổi để commit")

            # 3. QA and Reviewer are read-only: run in parallel.
            def run_qa():
                r.step("qa", "running", f"vòng {rounds + 1}")
                rep = agents.qa(spec, views["qa"])
                rep.checks += team.backend_checks(spec, views["qa"])
                rep.passed = all(c.passed for c in rep.checks)
                return rep

            def run_review():
                r.step("reviewer", "running", f"vòng {rounds + 1}")
                return team.reviewer(r.llm, spec, views["reviewer"])

            with ThreadPoolExecutor(max_workers=2) as pool:
                fq, fr = pool.submit(run_qa), pool.submit(run_review)
                report, review = fq.result(), fr.result()
            r.save("qa", report.model_dump())
            r.save("review", review.model_dump() | {"passed": review.passed})
            r.step("qa", "done" if report.passed else "failed",
                   f"{sum(c.passed for c in report.checks)}/{len(report.checks)} đạt")
            r.step("reviewer", "done" if review.passed else "failed",
                   f"{len(review.blocking())} lỗi chặn, {len(review.findings)} ghi chú")
            if report.passed and review.passed:
                break

            # Route every failure to the dev who owns it.
            issues = report.failures() + [
                Check(name=f"Review {f.rule} ({f.file})", passed=False, detail=f.message, owner=f.owner)
                for f in review.blocking()]
            front_fail = [c for c in issues if c.owner == "frontend_dev"]
            back_fail = [c for c in issues if c.owner == "backend_dev"]
            need_front = bool(front_fail)
            sink.event(pid, f"Trả {len(front_fail)} lỗi cho Frontend, {len(back_fail)} lỗi cho Backend")
            if rounds >= MAX_FIX_ROUNDS:
                stage = "qa" if not report.passed else "reviewer"
                r.step(stage, "blocked", f"vượt {MAX_FIX_ROUNDS} vòng sửa, cần sếp")
                break
            rounds += 1

        escalated = not (report.passed and review.passed)
        # Quality scorecard: did each dev's work pass on the first try, and how many rounds did it take?
        all_issues = report.failures() + review.blocking()
        r.metric("frontend_dev", "first_pass", 1.0 if front_rounds == 1 and not (escalated and any(
            i.owner == "frontend_dev" for i in all_issues)) else 0.0)
        r.metric("frontend_dev", "rounds", front_rounds)
        if spec.api:
            r.metric("backend_dev", "first_pass", 1.0 if back_rounds == 1 and not (escalated and any(
                i.owner == "backend_dev" for i in all_issues)) else 0.0)
            r.metric("backend_dev", "rounds", back_rounds)
        r.metric("qa", "checks", len(report.checks))
        r.metric("reviewer", "findings", len(review.findings))
        r.metric("reviewer", "blocking_findings", len(review.blocking()))
        r.step("reporter", "running")
        final = agents.reporter(r.llm, brief, spec, report, rounds, r.cost.to_dict(), escalated, option, review,
                                _memory(sink, pid))
        r.save("report", final.model_dump())
        r.save("git", {"log": ws.log(), "path": str(ws.dir)})
        r.step("reporter", "done")
        return r.end("needs_review" if escalated else "awaiting_approval")
    return r.status or "failed"


def run_project(pid: str, message: str, sink: Sink, workspace_root: Path, budget_usd: float = 2.0,
                llm_factory: LLMFactory = make_llm, choose: str = "recommended") -> str:
    """Plan and build in one go, picking an option automatically (CLI and tests)."""
    status = plan_project(pid, message, sink, budget_usd, llm_factory)
    if status != "awaiting_choice":
        return status
    proposal = Proposal(**sink.load(pid, "proposal"))
    option_id = proposal.recommended if choose == "recommended" else choose
    return build_project(pid, option_id, sink, workspace_root, budget_usd, llm_factory)
