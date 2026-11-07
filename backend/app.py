"""HTTP API for the boss UI.

POST /api/projects            start a project from a message
GET  /api/projects            list projects
GET  /api/projects/{id}       task board, artifacts, events, cost
POST /api/projects/{id}/choice     pick an option, or send feedback to revise them (checkpoint 1)
POST /api/projects/{id}/decision   approve / reject the delivery (checkpoint 2)
POST /api/projects/{id}/budget     approve more budget for a run that hit the ceiling, or stop it
POST /api/projects/{id}/deploy     deploy the approved commit to production (checkpoint)
POST /api/projects/{id}/github     push the approved commit to the client's GitHub (checkpoint)
POST /api/projects/{id}/client-message        draft the hand-over email again
PUT  /api/projects/{id}/client-message        boss edits the draft
POST /api/projects/{id}/client-message/send   send it to the client (checkpoint)
GET  /api/projects/{id}/export     zip of the approved project (its own git repo included)
GET  /api/clients                  clients with project counts
GET  /api/clients/{id}             client memory: past projects and remembered decisions
POST /api/clients/{id}/notes       remember a preference or fact about a client
GET  /api/agents/scorecard         quality numbers per agent
GET  /preview/{id}/{path}     serve the generated site from the workspace (working copy)
GET  /staging/{id}/  /live/{id}/   deployed snapshots; POST to their api/... stores form submissions
WS   /ws/events               live office feed for the pixel dashboard (see backend/office.py)
"""
from __future__ import annotations

import os
import threading
from pathlib import Path

import asyncio
import io
import json
import re
import subprocess
import time
import zipfile

from typing import Literal

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from ai import agents
from ai.agents import extract_client_name
from ai.artifacts import Brief, FinalReport, Proposal, Spec
from ai.llm import BudgetExceeded, CostTracker, make_llm
from ai.orchestrator import build_project, plan_project, resume_project, revise_options

ROOT = Path(__file__).resolve().parent.parent
WORKSPACE = Path(os.environ.get("VTD_WORKSPACE", ROOT / "workspace" / "projects"))
DB_PATH = Path(os.environ.get("VTD_DB", ROOT / "backend" / "data" / "vtd.sqlite3"))
DEFAULT_BUDGET = float(os.environ.get("VTD_DEFAULT_BUDGET_USD", "2.0"))

COMPANY = os.environ.get("VTD_COMPANY", "AtusCompany")

from . import delivery  # noqa: E402
from .delivery import DeliveryError  # noqa: E402
from .office import Office, OfficeSink, build_scorecard  # noqa: E402
from .store import Store  # noqa: E402

store = Store(DB_PATH)
office = Office()
office.metrics_provider = lambda: build_scorecard(store)
sink = OfficeSink(store, office)
app = FastAPI(title="Virtual Tech Dept")
llm_factory = make_llm  # tests swap this for a fake model


def _llm(cost: CostTracker):
    return llm_factory(cost)


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


class BudgetDecision(BaseModel):
    approve: bool
    add_usd: float = Field(default=0, ge=0, le=50, description="Số USD cấp thêm")
    note: str = Field(default="", max_length=500)


class DeployRequest(BaseModel):
    env: Literal["production"] = "production"
    confirm: bool = Field(description="Sếp xác nhận deploy production")


class PushRequest(BaseModel):
    repo: str = Field(max_length=201, description="chủ-sở-hữu/tên-repo trên GitHub của khách")
    branch: str = Field(default="main", max_length=100)
    confirm: bool


class MessageEdit(BaseModel):
    to: str = Field(default="", max_length=200)
    subject: str = Field(min_length=3, max_length=200)
    body: str = Field(min_length=10, max_length=10000)


class SendRequest(BaseModel):
    confirm: bool


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
    _bg(plan_project, pid, message, sink, budget, _llm)
    return pid


def _bg(fn, *args) -> None:
    threading.Thread(target=fn, args=args, daemon=True).start()


class _StagingSink:
    """Deploys staging before the project shows as ready, so the boss never sees a missing demo link."""

    def __init__(self, inner):
        self.inner = inner

    def __getattr__(self, name):
        return getattr(self.inner, name)

    def finish(self, pid: str, status: str, cost: dict) -> None:
        _after_build(pid, status)
        self.inner.finish(pid, status, cost)


def _build(pid: str, option_id: str, budget: float) -> None:
    build_project(pid, option_id, _StagingSink(sink), WORKSPACE, budget, _llm)


def _resume(pid: str, budget: float) -> None:
    resume_project(pid, _StagingSink(sink), WORKSPACE, budget, _llm)


def _after_build(pid: str, status: str) -> None:
    """A finished build goes to staging automatically: an internal link, not visible to the client yet."""
    if status not in ("awaiting_approval", "needs_review"):
        return
    try:
        rec = delivery.deploy(pid, WORKSPACE / pid, "staging")
    except (DeliveryError, OSError, subprocess.SubprocessError) as e:
        store.event(pid, f"Không deploy được staging: {e}")
        return
    _record(pid, "staging", rec)
    store.event(pid, f"Deploy staging commit {rec['sha'][:7]}: {rec['url']}")


def _delivery(pid: str) -> dict:
    return store.load(pid, "delivery") or {"history": []}


def _record(pid: str, key: str, rec: dict) -> dict:
    d = _delivery(pid)
    if key in ("staging", "production"):
        d[key] = rec
    d["history"] = (d.get("history") or []) + [{"kind": key, **rec}]
    store.artifact(pid, "delivery", d)
    return d


def _require(pid: str, status: str = "approved") -> dict:
    p = store.get(pid)
    if not p:
        raise HTTPException(404, "Không tìm thấy dự án")
    if p["status"] != status:
        raise HTTPException(409, "Sếp cần duyệt bàn giao trước" if status == "approved"
                            else f"Dự án đang ở trạng thái {p['status']}")
    return p


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
        _bg(_build, pid, body.option_id, p["budget_usd"])
        return {"status": "running", "action": "build"}
    if not body.note.strip():
        raise HTTPException(400, "Cần chọn một phương án hoặc ghi góp ý")
    if not store.transition(pid, "awaiting_choice", "running"):
        raise HTTPException(409, "Dự án vừa được xử lý")
    store.remember(pid, "revision", body.note.strip())
    _bg(revise_options, pid, body.note.strip(), sink, p["budget_usd"], _llm)
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
    if body.approve:
        # Pin what the boss looked at: production and the client's GitHub get exactly this commit.
        d = _delivery(pid)
        try:
            d["approved_sha"] = (d.get("staging") or {}).get("sha") or delivery.head_sha(WORKSPACE / pid)
        except DeliveryError:
            d["approved_sha"] = None
        store.artifact(pid, "delivery", d)
        _bg(_draft_message, pid)
    store.metric(pid, "reporter", "boss_approved", 1.0 if body.approve else 0.0)
    office.add_log("leader", "done" if body.approve else "blocked",
                   f"Sếp {'duyệt' if body.approve else 'yêu cầu sửa'}: {p['title'][:60]}")
    store.event(pid, f"Sếp {'duyệt' if body.approve else 'yêu cầu sửa'}" + (f": {body.note}" if body.note else ""))
    return {"status": status}


@app.post("/api/projects/{pid}/budget")
def budget(pid: str, body: BudgetDecision) -> dict:
    """Checkpoint: spending more than the project's ceiling needs the boss."""
    p = _require(pid, "over_budget")
    if not body.approve:
        if not store.transition(pid, "over_budget", "stopped"):
            raise HTTPException(409, "Dự án vừa được xử lý")
        store.remember(pid, "stopped", body.note.strip() or "Dừng dự án khi chạm trần ngân sách")
        store.event(pid, "Sếp dừng dự án ở trần ngân sách")
        return {"status": "stopped"}
    if body.add_usd <= 0:
        raise HTTPException(400, "Cần nhập số tiền cấp thêm")
    new_budget = round(p["budget_usd"] + body.add_usd, 4)
    if not store.transition(pid, "over_budget", "running"):
        raise HTTPException(409, "Dự án vừa được xử lý")
    store.set_budget(pid, new_budget)
    store.remember(pid, "budget", f"Duyệt chi thêm ${body.add_usd:.2f}, trần mới ${new_budget:.2f}"
                   + (f": {body.note.strip()}" if body.note.strip() else ""))
    office.add_log("leader", "done", f"Sếp duyệt chi thêm ${body.add_usd:.2f}: {p['title'][:60]}")
    _bg(_resume, pid, new_budget)
    return {"status": "running", "budget_usd": new_budget}


@app.post("/api/projects/{pid}/deploy")
def deploy_production(pid: str, body: DeployRequest) -> dict:
    """Checkpoint: production only with the boss's explicit confirmation, and only the approved commit."""
    _require(pid)
    if not body.confirm:
        raise HTTPException(400, "Cần sếp xác nhận deploy production")
    sha = _delivery(pid).get("approved_sha")
    if not sha:
        raise HTTPException(409, "Chưa có bản đã duyệt để deploy")
    try:
        rec = delivery.deploy(pid, WORKSPACE / pid, "production", sha)
    except DeliveryError as e:
        raise HTTPException(400, str(e)) from e
    _record(pid, "production", rec)
    store.remember(pid, "deployed", f"Deploy production commit {sha[:7]}: {rec['url']}")
    store.event(pid, f"Sếp duyệt deploy production commit {sha[:7]}: {rec['url']}")
    office.add_log("leader", "done", f"Deploy production: {rec['url']}")
    return rec


@app.post("/api/projects/{pid}/github")
def push_github(pid: str, body: PushRequest) -> dict:
    """Checkpoint: hand the code over by pushing the approved commit to the client's repository."""
    _require(pid)
    if not body.confirm:
        raise HTTPException(400, "Cần sếp xác nhận đẩy code cho khách")
    sha = _delivery(pid).get("approved_sha")
    if not sha:
        raise HTTPException(409, "Chưa có bản đã duyệt để đẩy")
    try:
        rec = delivery.push(WORKSPACE / pid, body.repo.strip(), body.branch.strip(), sha)
    except DeliveryError as e:
        raise HTTPException(400, str(e)) from e
    _record(pid, "github", rec)
    store.remember(pid, "pushed", f"Đẩy code lên {rec['repo']} nhánh {rec['branch']}")
    store.event(pid, f"Đẩy commit {sha[:7]} lên GitHub {rec['repo']} ({rec['branch']})")
    office.add_log("leader", "done", f"Giao code lên GitHub {rec['repo']}")
    return rec


def _shop_admin(pid: str) -> dict:
    p = _require(pid)
    spec = p["artifacts"].get("final_spec") or {}
    if spec.get("kind") != "shop" or "admin_orders" not in spec.get("features", []):
        raise HTTPException(404, "Dự án không có trang quản lý đơn")
    return p


@app.get("/api/projects/{pid}/admin-token")
def shop_admin_token(pid: str) -> dict:
    """The access code the boss hands to the client for admin.html. Only after approval."""
    _shop_admin(pid)
    store.event(pid, "Sếp xem mã truy cập trang quản lý đơn")
    return {"token": delivery.admin_token(pid)}


@app.get("/api/projects/{pid}/orders")
def shop_orders(pid: str, env: Literal["staging", "production"] = "production") -> dict:
    """Orders on the deployed shop, read through the shop's own admin API."""
    _shop_admin(pid)
    if delivery.site_file(pid, env, "") is None:
        return {"env": env, "deployed": False, "orders": []}
    status, _, body = delivery.proxy(pid, env, "GET", "admin/orders", "", b"",
                                     {"authorization": f"Bearer {delivery.admin_token(pid)}"})
    if status != 200:
        raise HTTPException(502, f"Backend của shop trả {status}")
    return {"env": env, "deployed": True, "orders": json.loads(body).get("orders", [])}


class _NoModel:
    """Used when the budget is spent: agents fall back to their templates without a model call."""

    def structured(self, *args, **kwargs):
        return None


def _draft_message(pid: str) -> dict:
    p = store.get(pid)
    a = p["artifacts"]
    proposal = Proposal(**a["proposal"]) if a.get("proposal") else None
    option = proposal.get((a.get("choice") or {}).get("option_id", "")) if proposal else None
    d = a.get("delivery") or {}
    links = {}
    if d.get("production"):
        links["Bản chạy thật"] = d["production"]["url"]
    elif d.get("staging"):
        links["Bản demo"] = d["staging"]["url"]
    client = p.get("client") or {"name": "Quý khách", "contact": ""}
    cost = CostTracker.from_dict(p["cost"], p["budget_usd"])
    args = (Brief(**a["brief"]), Spec(**a.get("final_spec") or a["spec"]), option, FinalReport(**a["report"]),
            links, client["name"])
    try:
        msg = agents.client_message(_llm(cost), *args)
        store.set_cost(pid, cost.to_dict())
        store.artifact(pid, "cost", cost.to_dict())
    except BudgetExceeded:
        store.event(pid, "Hết ngân sách, email cho khách dùng mẫu soạn sẵn")
        msg = agents.client_message(_NoModel(), *args)
    draft = {"to": delivery.email_in(client.get("contact", "")), **msg.model_dump(),
             "links": links, "drafted_at": time.strftime("%Y-%m-%d %H:%M:%S"), "edited": False}
    store.artifact(pid, "client_message", draft)
    store.event(pid, "Báo cáo viên soạn xong email gửi khách, chờ sếp duyệt")
    return draft


@app.post("/api/projects/{pid}/client-message")
def redraft_message(pid: str) -> dict:
    _require(pid)
    return _draft_message(pid)


@app.put("/api/projects/{pid}/client-message")
def edit_message(pid: str, body: MessageEdit) -> dict:
    _require(pid)
    draft = store.load(pid, "client_message") or {}
    draft.update(to=body.to.strip(), subject=body.subject.strip(), body=body.body.strip(), edited=True)
    store.artifact(pid, "client_message", draft)
    return draft


@app.post("/api/projects/{pid}/client-message/send")
def send_message(pid: str, body: SendRequest) -> dict:
    """Checkpoint: nothing reaches the client until the boss presses send."""
    _require(pid)
    if not body.confirm:
        raise HTTPException(400, "Cần sếp xác nhận gửi cho khách")
    draft = store.load(pid, "client_message")
    if not draft:
        raise HTTPException(409, "Chưa có email để gửi")
    try:
        rec = delivery.send_email(pid, draft.get("to", ""), draft["subject"], draft["body"])
    except DeliveryError as e:
        raise HTTPException(400, str(e)) from e
    draft["sent"] = rec
    store.artifact(pid, "client_message", draft)
    _record(pid, "email", rec)
    if rec["sent"]:
        store.remember(pid, "sent", f"Gửi email cho khách: {rec['subject']}")
        store.event(pid, f"Đã gửi email cho {rec['to']}")
        office.add_log("reporter", "done", f"Gửi email bàn giao cho {rec['to']}")
    else:
        store.event(pid, f"Chưa cấu hình SMTP: email cho {rec['to']} được lưu vào hộp thư đi ({rec['file']}), chưa gửi")
    return rec


def _serve_site(env: str, pid: str, path: str) -> Response:
    f = delivery.site_file(pid, env, path) if re.fullmatch(r"[\w-]{1,80}", pid) else None
    if f is None:
        raise HTTPException(404)
    return FileResponse(f)


async def _site_api(env: str, pid: str, path: str, request: Request) -> Response:
    """API calls on a deployed site go to that commit's own backend, running on a private port."""
    if not re.fullmatch(r"[\w-]{1,80}", pid) or delivery.site_file(pid, env, "") is None:
        raise HTTPException(404)
    status, headers, body = delivery.proxy(pid, env, request.method, path, request.url.query,
                                           await request.body(), dict(request.headers))
    return Response(body, status, headers={k: v for k, v in headers.items() if k != "content-type"},
                    media_type=headers.get("content-type"))


@app.api_route("/staging/{pid}/api/{path:path}", methods=["GET", "POST"], include_in_schema=False)
async def staging_api(pid: str, path: str, request: Request) -> Response:
    return await _site_api("staging", pid, path, request)


@app.api_route("/live/{pid}/api/{path:path}", methods=["GET", "POST"], include_in_schema=False)
async def live_api(pid: str, path: str, request: Request) -> Response:
    return await _site_api("production", pid, path, request)


@app.get("/staging/{pid}/{path:path}", include_in_schema=False)
def staging_site(pid: str, path: str = "") -> Response:
    return _serve_site("staging", pid, path)


@app.get("/live/{pid}/{path:path}", include_in_schema=False)
def live_site(pid: str, path: str = "") -> Response:
    return _serve_site("production", pid, path)


@app.get("/staging/{pid}", include_in_schema=False)
@app.get("/live/{pid}", include_in_schema=False)
def site_root(pid: str, request: Request) -> RedirectResponse:
    return RedirectResponse(request.url.path + "/")


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
