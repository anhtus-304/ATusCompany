"""HTTP API for the boss UI.

POST /api/projects            start a project from a message
GET  /api/projects            list projects
GET  /api/projects/{id}       task board, artifacts, events, cost
POST /api/projects/{id}/decision   approve / reject the delivery (human checkpoint)
GET  /preview/{id}/{path}     serve the generated site from the workspace
"""
from __future__ import annotations

import os
import threading
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from ai.orchestrator import run_project

ROOT = Path(__file__).resolve().parent.parent
WORKSPACE = Path(os.environ.get("VTD_WORKSPACE", ROOT / "workspace" / "projects"))
DB_PATH = Path(os.environ.get("VTD_DB", ROOT / "backend" / "data" / "vtd.sqlite3"))
DEFAULT_BUDGET = float(os.environ.get("VTD_DEFAULT_BUDGET_USD", "2.0"))

from .store import Store  # noqa: E402

store = Store(DB_PATH)
app = FastAPI(title="Virtual Tech Dept")


class NewProject(BaseModel):
    message: str = Field(min_length=5, max_length=5000)
    budget_usd: float | None = Field(default=None, gt=0, le=100)


class Decision(BaseModel):
    approve: bool
    note: str = ""


@app.post("/api/projects")
def create_project(body: NewProject) -> dict:
    budget = body.budget_usd or DEFAULT_BUDGET
    pid = store.create(body.message, budget)
    threading.Thread(target=run_project, args=(pid, body.message, store, WORKSPACE, budget),
                     daemon=True).start()
    return {"id": pid}


@app.get("/api/projects")
def list_projects() -> list[dict]:
    return store.list()


@app.get("/api/projects/{pid}")
def get_project(pid: str) -> dict:
    p = store.get(pid)
    if not p:
        raise HTTPException(404, "Không tìm thấy dự án")
    return p


@app.post("/api/projects/{pid}/decision")
def decide(pid: str, body: Decision) -> dict:
    p = store.get(pid)
    if not p:
        raise HTTPException(404, "Không tìm thấy dự án")
    if p["status"] not in ("awaiting_approval", "needs_review"):
        raise HTTPException(409, f"Dự án đang ở trạng thái {p['status']}, chưa thể duyệt")
    status = "approved" if body.approve else "changes_requested"
    store.set_status(pid, status)
    store.event(pid, f"Sếp {'duyệt' if body.approve else 'yêu cầu sửa'}" + (f": {body.note}" if body.note else ""))
    return {"status": status}


@app.get("/preview/{pid}/{path:path}")
def preview(pid: str, path: str = "") -> FileResponse:
    base = (WORKSPACE / pid).resolve()
    target = (base / (path or "index.html")).resolve()
    if base not in target.parents or ".git" in target.parts or not target.is_file():
        raise HTTPException(404)
    return FileResponse(target)


@app.get("/preview/{pid}")
def preview_root(pid: str) -> RedirectResponse:
    return RedirectResponse(f"/preview/{pid}/index.html")


app.mount("/", StaticFiles(directory=ROOT / "frontend", html=True), name="frontend")
