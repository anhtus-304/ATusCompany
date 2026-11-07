"""Phase-3 roles: UI/UX Designer, Backend Dev, QA runtime tests, Reviewer."""
from __future__ import annotations

import json
import os
import pprint
import re
import shutil
import socket
import tempfile
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from . import shop
from .agents import prompt
from .artifacts import (
    ApiEndpoint, ApiField, Check, CodeArtifact, DesignSpec, FileOut, Finding, ReviewReport,
    SectionDesign, Spec,
)
from .llm import LLM
from .workspace import RoleView

TEMPLATES = Path(__file__).parent / "templates"
TEST_TIMEOUT = int(os.environ.get("VTD_TEST_TIMEOUT", "60"))


# --------------------------------------------------------------------------- contract

def contact_endpoint() -> ApiEndpoint:
    return ApiEndpoint(method="POST", path="/api/contact", purpose="Lưu lời nhắn khách gửi từ form liên hệ",
                       fields=[ApiField(name="name", type="string", required=True, max_length=100),
                               ApiField(name="phone", type="phone", required=True, max_length=20),
                               ApiField(name="message", type="text", required=False, max_length=1000)])


# --------------------------------------------------------------------------- Designer

def _lum(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    rgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(a: str, b: str) -> float:
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _valid_hex(c: str) -> bool:
    return bool(re.fullmatch(r"#[0-9a-fA-F]{3}([0-9a-fA-F]{3})?", c or ""))


def _fix_palette(colors: dict[str, str], dark: bool) -> dict[str, str]:
    base = ({"brand": "#e9d8c4", "accent": "#d9a26b", "surface": "#171310", "ink": "#efe6dc", "muted": "#b9ab9c"}
            if dark else
            {"brand": "#3b2a20", "accent": "#a8652f", "surface": "#f6efe7", "ink": "#1f1a17", "muted": "#5c5047"})
    out = {k: (colors.get(k) if _valid_hex(colors.get(k, "")) else v) for k, v in base.items()}
    if contrast(out["ink"], out["surface"]) < 4.5:
        out["ink"] = base["ink"]
    if contrast(out["muted"], out["surface"]) < 4.5:
        out["muted"] = base["muted"]
    return out


def designer(llm: LLM, spec: Spec, ws: RoleView) -> DesignSpec:
    out = llm.structured("designer", prompt("designer"), f"Spec:\n{spec.model_dump_json(indent=2)}", DesignSpec)
    if out is None:
        pal = spec.palette + ["#3b2a20", "#a8652f", "#f6efe7", "#1f1a17"]
        layouts = {"hero": "hero", "faq": "faq", "about": "split", "products": "grid"}
        out = DesignSpec(
            colors={"brand": pal[0], "accent": pal[1], "surface": pal[2], "ink": pal[3], "muted": "#5c5047"},
            dark_colors={} if "dark_mode" not in spec.features else {"surface": "#171310"},
            font_stack='system-ui, -apple-system, "Segoe UI", Roboto, sans-serif',
            radius_px=10, max_width_px=1040,
            sections=[SectionDesign(id=s.id, layout=("form" if s.id == "contact" and "contact_form" in spec.features
                                                     else layouts.get(s.id, "grid" if i % 2 else "list")))
                      for i, s in enumerate(spec.sections)],
            notes=["Khoảng cách dọc giữa các mục 64px, 48px trên điện thoại",
                   "Nút CTA bo tròn, có trạng thái hover và viền focus rõ ràng",
                   "Cỡ chữ thân bài tối thiểu 16px, dòng 1.6",
                   "Ô nhập liệu có nhãn hiển thị, không chỉ dùng placeholder"],
        )
    # Guardrails the dev and QA rely on.
    out.colors = _fix_palette(out.colors, dark=False)
    if "dark_mode" in spec.features:
        out.dark_colors = _fix_palette(out.dark_colors, dark=True)
    by_id = {d.id: d for d in out.sections}
    out.sections = [by_id.get(s.id) or SectionDesign(id=s.id, layout="list") for s in spec.sections]
    out.sections[0].layout = "hero"
    ws.write("design/design.json", out.model_dump_json(indent=2))
    return out


# --------------------------------------------------------------------------- Backend Dev

def backend_dev(llm: LLM, spec: Spec, ws: RoleView, failures: list[str] | None = None,
                previous: CodeArtifact | None = None) -> CodeArtifact | None:
    if not spec.api:
        return None
    user = "API contract:\n" + json.dumps([e.model_dump() for e in spec.api], ensure_ascii=False, indent=2)
    if spec.kind == "shop":
        user += ("\n\nDanh mục (ghi nguyên vào api/products.json):\n"
                 + json.dumps([p.model_dump() for p in spec.products], ensure_ascii=False, indent=2)
                 + "\n\nTính năng: " + json.dumps(shop.flags(spec.features)))
    if failures:
        user += "\n\nLỗi cần sửa:\n" + "\n".join(f"- {f}" for f in failures)
        if previous:
            user += "\n\nCode lần trước:\n" + "\n\n".join(f"=== {f.path} ===\n{f.content}" for f in previous.files)
    system = prompt("backend_dev") + ("\n\n" + prompt("backend_dev_shop") if spec.kind == "shop" else "")
    out = llm.structured("backend_dev", system, user, CodeArtifact)
    if out is None and spec.kind == "shop":
        out = CodeArtifact(files=shop.backend_files(spec), notes="Sinh từ template offline (chế độ mock).")
    if out is None:
        endpoints = {e.path: {"fields": [f.model_dump() for f in e.fields], "success_status": e.success_status,
                              "store": e.path.strip("/").replace("/", "_") + ".jsonl"} for e in spec.api}
        server = (TEMPLATES / "api_server.py.tmpl").read_text(encoding="utf-8").replace(
            "__ENDPOINTS__", pprint.pformat(endpoints, indent=4, sort_dicts=False))
        tests = (TEMPLATES / "api_test.py.tmpl").read_text(encoding="utf-8")
        out = CodeArtifact(files=[FileOut(path="api/server.py", content=server),
                                  FileOut(path="api/test_server.py", content=tests)],
                           notes="Sinh từ template offline (chế độ mock).")
    for f in out.files:
        ws.write(f.path, f.content)
    return out


# --------------------------------------------------------------------------- QA runtime tests

def _sandbox_env() -> dict[str, str]:
    """Generated code never sees our secrets."""
    keep = ("PATH", "HOME", "LANG", "LC_ALL", "SYSTEMROOT", "TMPDIR", "TEMP")
    return {k: v for k, v in os.environ.items() if k in keep} | {"PYTHONDONTWRITEBYTECODE": "1"}


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def backend_checks(spec: Spec, ws: RoleView) -> list[Check]:
    """Runs the backend's own tests, then smoke-tests the real server process."""
    if not spec.api:
        return []
    checks: list[Check] = []

    def add(name: str, ok: bool, detail: str = "") -> None:
        checks.append(Check(name=name, passed=ok, detail="" if ok else detail[-800:], owner="backend_dev"))

    has = ws.exists("api/server.py") and ws.exists("api/test_server.py")
    add("Backend có api/server.py và api/test_server.py", has, "Thiếu file backend")
    if not has:
        return checks
    # Run against a throwaway copy so tests never touch the project's real data or git repo.
    with tempfile.TemporaryDirectory(prefix="vtd-qa-") as tmp:
        sandbox = Path(tmp) / "project"
        shutil.copytree(ws.dir, sandbox, ignore=shutil.ignore_patterns(".git", ".vtd", "data", "__pycache__"))
        _run_backend(spec, sandbox, add)
    return checks


def _run_backend(spec: Spec, cwd: Path, add) -> None:
    try:
        r = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "api", "-t", "api"],
                           cwd=cwd, capture_output=True, text=True, timeout=TEST_TIMEOUT, env=_sandbox_env())
        ran = re.search(r"Ran (\d+) test", r.stderr)
        n = int(ran.group(1)) if ran else 0
        add(f"Test backend chạy và đạt ({n} test)", r.returncode == 0 and n >= 3,
            (r.stderr or r.stdout) if r.returncode else f"Chỉ có {n} test, cần ít nhất 3")
    except subprocess.TimeoutExpired:
        add("Test backend chạy và đạt", False, f"Quá {TEST_TIMEOUT}s")

    port = _free_port()
    data_dir = cwd / ".qa-data"
    token = "qa-" + os.urandom(12).hex()
    # Same way production starts it: a data folder outside the code, and the admin code from the environment.
    proc = subprocess.Popen([sys.executable, "api/server.py", "--port", str(port), "--data", str(data_dir)], cwd=cwd,
                            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
                            env=_sandbox_env() | {"SHOP_ADMIN_TOKEN": token})
    base = f"http://127.0.0.1:{port}"
    try:
        up = False
        for _ in range(50):
            try:
                urllib.request.urlopen(base + "/", timeout=1)
                up = True
                break
            except (urllib.error.URLError, ConnectionError):
                if proc.poll() is not None:
                    break
                time.sleep(0.1)
        add("Server khởi động và phục vụ trang chủ", up,
            proc.stderr.read() if proc.poll() is not None and proc.stderr else "Không kết nối được")
        if up and spec.kind == "shop":
            shop.runtime_checks(spec, base, data_dir, token, add)
        elif up:
            for ep in spec.api:
                good = {f.name: {"phone": "0901234567", "email": "a@b.vn"}.get(f.type, "Khách thử") for f in ep.fields}
                st = _post(base + ep.path, good)
                add(f"{ep.method} {ep.path} nhận dữ liệu hợp lệ", st == ep.success_status,
                    f"Trả {st}, contract yêu cầu {ep.success_status}")
                req = [f.name for f in ep.fields if f.required]
                if req:
                    bad = dict(good)
                    bad.pop(req[0])
                    st = _post(base + ep.path, bad)
                    add(f"{ep.method} {ep.path} từ chối thiếu '{req[0]}'", st == 400, f"Trả {st}, cần 400")
            stored = [x for x in data_dir.rglob("*") if x.is_file()] if data_dir.is_dir() else []
            add("Dữ liệu được lưu vào thư mục --data", bool(stored), f"Không có file nào trong {data_dir.name}")
            st = _get_status(base + "/api/server.py")
            add("Không lộ mã nguồn backend qua HTTP", st == 404, f"/api/server.py trả {st}")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def _post(url: str, data: dict) -> int:
    req = urllib.request.Request(url, data=json.dumps(data).encode(), method="POST",
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except urllib.error.URLError:
        return 0


def _get_status(url: str) -> int:
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except urllib.error.URLError:
        return 0


# --------------------------------------------------------------------------- Reviewer

_SECRET = re.compile(r"(sk-[A-Za-z0-9_-]{16,}|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{20,}|"
                     r"(?i:(password|secret|api_key|token)\s*=\s*['\"][^'\"]{6,}['\"]))")
_PY_RULES = [
    (re.compile(r"\b(eval|exec)\s*\("), "blocker", "no-eval", "Không dùng eval/exec với dữ liệu"),
    (re.compile(r"shell\s*=\s*True|os\.system\s*\("), "blocker", "no-shell", "Không chạy lệnh shell"),
    (re.compile(r"\.execute\s*\(\s*f[\"']"), "blocker", "sql-injection", "Dùng tham số SQL, không ghép chuỗi"),
    (re.compile(r"pickle\.loads?\s*\("), "blocker", "unsafe-deserialize", "Không giải tuần tự dữ liệu không tin cậy"),
    (re.compile(r"traceback\.format_exc\(\)|str\(e\)\s*\}"), "major", "leak-errors", "Không trả chi tiết lỗi cho người dùng"),
    (re.compile(r"[\"']0\.0\.0\.0[\"']"), "minor", "bind-all", "Mặc định nên lắng nghe 127.0.0.1"),
]
_JS_RULES = [
    (re.compile(r"\b(eval|Function)\s*\(|setTimeout\s*\(\s*[\"']"), "blocker", "no-eval", "Không chạy chuỗi như code"),
    (re.compile(r"\.(innerHTML|outerHTML)\s*\+?=\s*(?![\"'`]\s*[\"'`];)"), "major", "xss-innerhtml",
     "Gán innerHTML từ dữ liệu dễ bị XSS, dùng textContent/createElement"),
    (re.compile(r"document\.write\s*\("), "major", "document-write", "Không dùng document.write"),
    (re.compile(r"localStorage\.setItem\([^)]*(token|password)", re.I), "major", "secret-storage",
     "Không lưu mã truy cập lâu dài trong localStorage"),
]
_HTML_RULES = [
    (re.compile(r"\son[a-z]+\s*=\s*[\"']", re.I), "major", "inline-handler", "Không dùng thuộc tính sự kiện nội tuyến"),
    (re.compile(r"href\s*=\s*[\"']\s*javascript:", re.I), "blocker", "javascript-url", "Không dùng liên kết javascript:"),
    (re.compile(r"<iframe", re.I), "minor", "iframe", "Tránh nhúng iframe bên ngoài"),
]


def _static_review(spec: Spec, ws: RoleView) -> list[Finding]:
    findings: list[Finding] = []
    for rel in ws.list_files():
        if rel.startswith("design/") or rel == ".gitignore":
            continue
        owner = "backend_dev" if rel.startswith("api/") else "frontend_dev"
        try:
            text = ws.read(rel)
        except UnicodeDecodeError:
            continue
        if _SECRET.search(text):
            findings.append(Finding(severity="blocker", owner=owner, file=rel, rule="hardcoded-secret",
                                    message="Có chuỗi giống khóa bí mật trong code, chuyển sang biến môi trường"))
        if rel.endswith(".py") and not rel.startswith("api/test_"):
            for rx, sev, rule, msg in _PY_RULES:
                if rx.search(text):
                    findings.append(Finding(severity=sev, owner=owner, file=rel, rule=rule, message=msg))
            if spec.api and rel == "api/server.py":
                if not re.search(r"max_length|MAX_BODY|Content-Length", text):
                    findings.append(Finding(severity="major", owner=owner, file=rel, rule="input-limits",
                                            message="Thiếu giới hạn độ dài trường hoặc kích thước body"))
        if rel.endswith(".js"):
            for rx, sev, rule, msg in _JS_RULES:
                if rx.search(text):
                    findings.append(Finding(severity=sev, owner=owner, file=rel, rule=rule, message=msg))
        if rel.endswith(".html"):
            for rx, sev, rule, msg in _HTML_RULES:
                if rx.search(text):
                    findings.append(Finding(severity=sev, owner=owner, file=rel, rule=rule, message=msg))
            for m in re.finditer(r"<a\b[^>]*target\s*=\s*[\"']_blank[\"'][^>]*>", text, re.I):
                if "noopener" not in m.group(0):
                    findings.append(Finding(severity="minor", owner=owner, file=rel, rule="noopener",
                                            message="Liên kết target=_blank cần rel=\"noopener\""))
            for m in re.finditer(r"<form\b[^>]*>(.*?)</form>", text, re.I | re.S):
                if re.search(r"<input(?![^>]*maxlength)(?![^>]*type=\"?(radio|checkbox|hidden|submit)\b)[^>]*>",
                             m.group(1), re.I):
                    findings.append(Finding(severity="minor", owner=owner, file=rel, rule="input-maxlength",
                                            message="Ô nhập nên có maxlength khớp contract"))
                    break
    return findings


def reviewer(llm: LLM, spec: Spec, ws: RoleView) -> ReviewReport:
    findings = _static_review(spec, ws)
    files = "\n\n".join(f"=== {f} ===\n{ws.read(f)}" for f in ws.list_files()
                        if f.endswith((".py", ".html", ".css", ".js", ".json")))
    out = llm.structured("reviewer", prompt("reviewer"),
                         f"Spec:\n{spec.model_dump_json(indent=2)}\n\nCode:\n{files}", ReviewReport)
    if out is not None:
        seen = {(f.file, f.rule) for f in findings}
        findings += [f for f in out.findings if (f.file, f.rule) not in seen]
    return ReviewReport(findings=findings)
