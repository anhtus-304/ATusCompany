"""HTTP API for the boss UI.

POST /api/projects            start a project from a message
GET  /api/projects            list projects
GET  /api/projects/{id}       task board, artifacts, events, cost
POST /api/projects/{id}/choice     pick an option, or send feedback to revise them (checkpoint 1)
POST /api/projects/{id}/decision   approve / reject the delivery (checkpoint 2)
GET  /api/projects/{id}/export     zip of the approved project (its own git repo included)
GET  /api/clients                  clients with project counts
GET  /api/clients/{id}             client memory: past projects and remembered decisions
POST /api/clients/{id}/notes       remember a preference or fact about a client
GET  /api/agents/scorecard         quality numbers per agent
GET  /preview/{id}/{path}     serve the generated site from the workspace
WS   /ws/events               live office feed for the pixel dashboard (see backend/office.py)
"""
from __future__ import annotations

import os
import threading
from pathlib import Path

import asyncio
import io
import zipfile

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from ai.agents import extract_client_name
from ai.orchestrator import build_project, plan_project, revise_options

ROOT = Path(__file__).resolve().parent.parent
WORKSPACE = Path(os.environ.get("VTD_WORKSPACE", ROOT / "workspace" / "projects"))
DB_PATH = Path(os.environ.get("VTD_DB", ROOT / "backend" / "data" / "vtd.sqlite3"))
DEFAULT_BUDGET = float(os.environ.get("VTD_DEFAULT_BUDGET_USD", "2.0"))

COMPANY = os.environ.get("VTD_COMPANY", "AtusCompany")

from .office import Office, OfficeSink, build_scorecard  # noqa: E402
from .store import Store  # noqa: E402

store = Store(DB_PATH)
office = Office()
office.metrics_provider = lambda: build_scorecard(store)
sink = OfficeSink(store, office)
app = FastAPI(title="Virtual Tech Dept")


class NewProject(BaseModel):
    message: str = Field(min_length=5, max_length=5000)
    budget_usd: float | None = Field(default=None, gt=0, le=100)
    client: str | None = Field(default=None, max_length=80, description="Tên khách; bỏ trống thì lấy tên trong ngoặc kép")


class ClientNote(BaseModel):
    text: str = Field(min_length=2, max_length=1000)


class ClientUpdate(BaseModel):
    contact: str = Field(default="", max_length=200)


class Choice(BaseModel):
    option_id: str | None = Field(default=None, description="Chọn phương án này để thực thi")
    note: str = Field(default="", max_length=2000, description="Góp ý để chỉnh lại các phương án")


class Decision(BaseModel):
    approve: bool
    note: str = ""


@app.post("/api/projects")
def create_project(body: NewProject) -> dict:
    return {"id": start_project(body.message, body.budget_usd, client=body.client)}


def start_project(message: str, budget_usd: float | None = None, assignee: str = "leader",
                  client: str | None = None) -> str:
    budget = budget_usd or DEFAULT_BUDGET
    name = (client or "").strip() or extract_client_name(message) or "Khách lẻ"
    cid = store.find_or_create_client(name)
    pid = store.create(message, budget, cid)
    store.artifact(pid, "memory", store.client_memory(cid, exclude_project=pid))
    if assignee not in office.agents:
        assignee = "leader"
    office.add_log(assignee, "assign", f"Sếp giao việc: {message[:120]}")
    _bg(plan_project, pid, message, sink, budget)
    return pid


def _bg(fn, *args) -> None:
    threading.Thread(target=fn, args=args, daemon=True).start()


@app.post("/api/projects/{pid}/choice")
def choose(pid: str, body: Choice) -> dict:
    p = store.get(pid)
    if not p:
        raise HTTPException(404, "Không tìm thấy dự án")
    if p["status"] != "awaiting_choice":
        raise HTTPException(409, f"Dự án đang ở trạng thái {p['status']}, không chờ chọn phương án")
    if body.option_id:
        proposal = p["artifacts"].get("proposal") or {}
        if body.option_id not in {o["id"] for o in proposal.get("options", [])}:
            raise HTTPException(400, f"Không có phương án {body.option_id}")
        if not store.transition(pid, "awaiting_choice", "running"):
            raise HTTPException(409, "Dự án vừa được xử lý")
        store.event(pid, f"Sếp chọn phương án {body.option_id}")
        opt = next(o for o in proposal["options"] if o["id"] == body.option_id)
        store.remember(pid, "choice", f"Chọn {opt['id']} {opt['name']} ({opt['tier']}), "
                                      f"{opt['est_price_vnd']:,} VND, {opt['est_days']:g} ngày")
        _bg(build_project, pid, body.option_id, sink, WORKSPACE, p["budget_usd"])
        return {"status": "running", "action": "build"}
    if not body.note.strip():
        raise HTTPException(400, "Cần chọn một phương án hoặc ghi góp ý")
    if not store.transition(pid, "awaiting_choice", "running"):
        raise HTTPException(409, "Dự án vừa được xử lý")
    store.remember(pid, "revision", body.note.strip())
    _bg(revise_options, pid, body.note.strip(), sink, p["budget_usd"])
    return {"status": "running", "action": "revise"}


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
    if not store.transition(pid, p["status"], status):
        raise HTTPException(409, "Dự án vừa được xử lý")
    store.remember(pid, status, body.note.strip() or ("Duyệt gửi khách" if body.approve else "Yêu cầu sửa"))
    store.metric(pid, "reporter", "boss_approved", 1.0 if body.approve else 0.0)
    office.add_log("leader", "done" if body.approve else "blocked",
                   f"Sếp {'duyệt' if body.approve else 'yêu cầu sửa'}: {p['title'][:60]}")
    store.event(pid, f"Sếp {'duyệt' if body.approve else 'yêu cầu sửa'}" + (f": {body.note}" if body.note else ""))
    return {"status": status}


# Never serve these from a project: git internals, backend source, and stored customer data.
PRIVATE_DIRS = {".git", ".vtd", "api"}


@app.get("/preview/{pid}/{path:path}")
def preview(pid: str, path: str = "") -> FileResponse:
    base = (WORKSPACE / pid).resolve()
    target = (base / (path or "index.html")).resolve()
    if base not in target.parents or not target.is_file():
        raise HTTPException(404)
    if PRIVATE_DIRS & set(target.relative_to(base).parts):
        raise HTTPException(404)
    return FileResponse(target)


@app.get("/api/projects/{pid}/export")
def export(pid: str) -> Response:
    """Delivery package for the client. Only after the boss approved it; customer data is never included."""
    p = store.get_meta(pid)
    if not p:
        raise HTTPException(404, "Không tìm thấy dự án")
    if p["status"] != "approved":
        raise HTTPException(409, "Sếp cần duyệt trước khi xuất bản giao khách")
    base = (WORKSPACE / pid).resolve()
    if not base.is_dir():
        raise HTTPException(404, "Không có sản phẩm")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(base.rglob("*")):
            rel = f.relative_to(base)
            if f.is_file() and not ({".vtd", "__pycache__"} & set(rel.parts)) and rel.parts[:2] != ("api", "data"):
                z.write(f, f"{pid}/{rel}")
    store.event(pid, "Xuất gói giao khách")
    return Response(buf.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{pid}.zip"'})


@app.get("/api/clients")
def list_clients() -> list[dict]:
    return store.clients()


@app.get("/api/clients/{cid}")
def client_detail(cid: int) -> dict:
    c = store.get_client(cid)
    if not c:
        raise HTTPException(404, "Không tìm thấy khách hàng")
    return {**c, "memory": store.client_memory(cid)}


@app.post("/api/clients/{cid}/notes")
def add_client_note(cid: int, body: ClientNote) -> dict:
    if not store.get_client(cid):
        raise HTTPException(404, "Không tìm thấy khách hàng")
    store.remember(None, "note", body.text.strip(), client_id=cid)
    return {"ok": True}


@app.patch("/api/clients/{cid}")
def update_client(cid: int, body: ClientUpdate) -> dict:
    if not store.get_client(cid):
        raise HTTPException(404, "Không tìm thấy khách hàng")
    store.update_client(cid, body.contact.strip())
    return store.get_client(cid)


@app.get("/api/agents/scorecard")
def scorecard() -> dict:
    return build_scorecard(store)


@app.get("/preview/{pid}")
def preview_root(pid: str) -> RedirectResponse:
    return RedirectResponse(f"/preview/{pid}/index.html")


@app.websocket("/ws/events")
async def ws_events(ws: WebSocket) -> None:
    await ws.accept()
    queue = office.subscribe()
    try:
        await ws.send_json(office.snapshot(COMPANY))

        async def pump() -> None:
            while True:
                await ws.send_json(await queue.get())

        sender = asyncio.create_task(pump())
        try:
            while True:
                msg = await ws.receive_json()
                if isinstance(msg, dict) and msg.get("type") == "assign":
                    text = str(msg.get("text", "")).strip()
                    if 5 <= len(text) <= 5000:
                        start_project(text, assignee=str(msg.get("to") or "leader"))
                    else:
                        office.add_log(None, "error", "Nội dung giao việc phải từ 5 đến 5000 ký tự")
        finally:
            sender.cancel()
    except (WebSocketDisconnect, RuntimeError, ValueError):
        pass
    finally:
        office.unsubscribe(queue)


app.mount("/", StaticFiles(directory=ROOT / "frontend", html=True), name="frontend")
