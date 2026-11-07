"""Phase-1 pipeline: message -> brief -> spec -> code -> QA (with fix loop) -> report.

The orchestrator owns sequencing and the task board. Agents only see the
artifacts they need. QA failures go back to the dev, never straight to the
boss, up to MAX_FIX_ROUNDS; past that the project is escalated.
"""
from __future__ import annotations

import os
import traceback
from pathlib import Path
from typing import Callable, Protocol

from . import agents
from .llm import BudgetExceeded, CostTracker, LLM, make_llm
from .workspace import Workspace

MAX_FIX_ROUNDS = int(os.environ.get("VTD_MAX_FIX_ROUNDS", "2"))

STAGES = [
    ("intake", "Lễ tân"),
    ("analyst", "BA / Architect"),
    ("frontend_dev", "Frontend Dev"),
    ("qa", "QA"),
    ("reporter", "Báo cáo viên"),
]


class Sink(Protocol):
    """Where the orchestrator reports progress (the backend store, or a CLI printer)."""

    def task(self, project_id: str, stage: str, status: str, note: str = "") -> None: ...
    def artifact(self, project_id: str, name: str, data: dict) -> None: ...
    def event(self, project_id: str, text: str) -> None: ...
    def finish(self, project_id: str, status: str, cost: dict) -> None: ...


def run_project(project_id: str, message: str, sink: Sink, workspace_root: Path,
                budget_usd: float = 2.0, llm_factory: Callable[[CostTracker], LLM] = make_llm) -> str:
    cost = CostTracker(budget_usd=budget_usd)
    llm = llm_factory(cost)
    ws = Workspace(workspace_root, project_id)
    sink.event(project_id, f"Bắt đầu dự án, model: {llm.name}, trần ngân sách ${budget_usd:.2f}")
    stage = "intake"

    def step(name: str, status: str, note: str = "") -> None:
        nonlocal stage
        stage = name
        sink.task(project_id, name, status, note)

    try:
        step("intake", "running")
        brief = agents.intake(llm, message)
        sink.artifact(project_id, "brief", brief.model_dump())
        step("intake", "done", f"{len(brief.open_questions)} câu hỏi mở")

        step("analyst", "running")
        spec = agents.analyst(llm, brief)
        sink.artifact(project_id, "spec", spec.model_dump())
        step("analyst", "done", f"{len(spec.sections)} mục")

        dev_view, qa_view = ws.for_role("frontend_dev"), ws.for_role("qa")
        code, failures, rounds = None, None, 0
        while True:
            step("frontend_dev", "running", f"vòng {rounds + 1}")
            code = agents.frontend_dev(llm, spec, dev_view, failures, code)
            sha = ws.commit(f"frontend_dev: round {rounds + 1}" + (" (fix QA)" if failures else ""))
            sink.task(project_id, "frontend_dev", "done", f"commit {sha}" if sha else "không đổi")

            step("qa", "running", f"vòng {rounds + 1}")
            report = agents.qa(spec, qa_view)
            sink.artifact(project_id, "qa", report.model_dump())
            if report.passed:
                sink.task(project_id, "qa", "done", f"{len(report.checks)}/{len(report.checks)} đạt")
                break
            failures = report.failures()
            sink.event(project_id, f"QA trả {len(failures)} lỗi về cho dev")
            if rounds >= MAX_FIX_ROUNDS:
                sink.task(project_id, "qa", "blocked", f"vượt {MAX_FIX_ROUNDS} vòng sửa, cần sếp")
                break
            sink.task(project_id, "qa", "failed", f"{len(failures)} lỗi, trả về dev")
            rounds += 1

        escalated = not report.passed
        step("reporter", "running")
        final = agents.reporter(llm, brief, spec, report, rounds, cost.to_dict(), escalated)
        sink.artifact(project_id, "report", final.model_dump())
        sink.artifact(project_id, "git", {"log": ws.log(), "path": str(ws.dir)})
        step("reporter", "done")

        status = "needs_review" if escalated else "awaiting_approval"
        sink.finish(project_id, status, cost.to_dict())
        return status
    except BudgetExceeded as e:
        sink.task(project_id, stage, "blocked", str(e))
        sink.event(project_id, f"Dừng vì chạm trần ngân sách: {e}")
        sink.finish(project_id, "over_budget", cost.to_dict())
        return "over_budget"
    except Exception as e:  # noqa: BLE001 - surface any agent failure on the board
        sink.task(project_id, stage, "failed", f"{type(e).__name__}: {e}")
        sink.event(project_id, traceback.format_exc(limit=3))
        sink.finish(project_id, "failed", cost.to_dict())
        return "failed"
