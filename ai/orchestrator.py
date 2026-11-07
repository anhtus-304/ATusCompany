"""Pipeline, in two halves split by the boss's decision.

plan_project:   message -> brief -> spec -> 3 options        -> pause "awaiting_choice"
revise_options: boss feedback -> new options                  -> pause "awaiting_choice"
build_project:  chosen option -> final spec -> code -> QA (fix loop) -> report
                                                              -> pause "awaiting_approval"

The orchestrator owns sequencing and the task board. Agents only see the
artifacts they need. QA failures go back to the dev, never straight to the
boss, up to MAX_FIX_ROUNDS; past that the project is escalated.
"""
from __future__ import annotations

import os
import traceback
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterator, Protocol

from . import agents
from .artifacts import Brief, Proposal, Spec
from .llm import BudgetExceeded, CostTracker, LLM, make_llm
from .workspace import Workspace

MAX_FIX_ROUNDS = int(os.environ.get("VTD_MAX_FIX_ROUNDS", "2"))
MAX_REVISIONS = int(os.environ.get("VTD_MAX_REVISIONS", "3"))

STAGES = [
    ("intake", "Lễ tân"),
    ("analyst", "BA / Architect"),
    ("proposer", "Đề xuất phương án"),
    ("choice", "Sếp chọn"),
    ("frontend_dev", "Frontend Dev"),
    ("qa", "QA"),
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


class _Run:
    """Shared plumbing for one orchestrator call: cost, llm, current stage, error handling."""

    def __init__(self, pid: str, sink: Sink, budget_usd: float, llm_factory: LLMFactory):
        self.pid, self.sink = pid, sink
        saved = sink.load(pid, "cost") or {}
        self.cost = CostTracker.from_dict(saved, budget_usd)
        self.llm = llm_factory(self.cost)
        self.stage = "intake"
        self.status: str | None = None

    def step(self, stage: str, status: str, note: str = "") -> None:
        self.stage = stage
        self.sink.task(self.pid, stage, status, note)

    def save(self, name: str, data: dict) -> None:
        self.sink.artifact(self.pid, name, data)

    def end(self, status: str) -> str:
        self.status = status
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
    proposal = agents.proposer(r.llm, brief, spec, note, previous)
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
        brief = agents.intake(r.llm, message)
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
        dev_view, qa_view = ws.for_role("frontend_dev"), ws.for_role("qa")
        code, failures, rounds = None, None, 0
        while True:
            r.step("frontend_dev", "running", f"vòng {rounds + 1}")
            code = agents.frontend_dev(r.llm, spec, dev_view, failures, code)
            sha = ws.commit(f"frontend_dev: option {option.id}, round {rounds + 1}"
                            + (" (fix QA)" if failures else ""))
            r.step("frontend_dev", "done", f"commit {sha}" if sha else "không đổi")

            r.step("qa", "running", f"vòng {rounds + 1}")
            report = agents.qa(spec, qa_view)
            r.save("qa", report.model_dump())
            if report.passed:
                r.step("qa", "done", f"{len(report.checks)}/{len(report.checks)} đạt")
                break
            failures = report.failures()
            sink.event(pid, f"QA trả {len(failures)} lỗi về cho dev")
            if rounds >= MAX_FIX_ROUNDS:
                r.step("qa", "blocked", f"vượt {MAX_FIX_ROUNDS} vòng sửa, cần sếp")
                break
            r.step("qa", "failed", f"{len(failures)} lỗi, trả về dev")
            rounds += 1

        escalated = not report.passed
        r.step("reporter", "running")
        final = agents.reporter(r.llm, brief, spec, report, rounds, r.cost.to_dict(), escalated, option)
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
