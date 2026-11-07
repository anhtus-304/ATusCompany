"""Delivery: staging and production deploys, pushing to the client's GitHub, sending the client message.

Every outward step in this module runs only from an explicit boss action in backend/app.py.
Agents in ai/ never import it: devs write code, they don't deploy or send anything.

Deploys are snapshots of one git commit of the project repo (`git archive`), never of the
working folder, so production is exactly the commit the boss approved on staging. Only the
static site is published: backend source, design files, git internals and stored customer
data stay out. Form posts on a deployed site are validated against the Architect's API
contract and stored outside the published folder.
"""
from __future__ import annotations

import atexit
import base64
import http.client
import io
import json
import os
import re
import shutil
import secrets
import smtplib
import socket
import subprocess
import sys
import tarfile
import threading
import time
import uuid
from email.message import EmailMessage
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent.parent
ENVS = ("staging", "production")
# Top-level folders of a project that are not part of the public site.
PRIVATE_TOP = {"api", "design"}
MAX_BODY = 16 * 1024
EMAIL_RE = re.compile(r"^[^@\s<>,;]+@[^@\s<>,;]+\.[^@\s<>,;]+$")
REPO_RE = re.compile(r"^[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}$")
BRANCH_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,99}$")
_lock = threading.Lock()


class DeliveryError(RuntimeError):
    pass


def deploy_root() -> Path:
    return Path(os.environ.get("VTD_DEPLOYS", ROOT / "workspace" / "deploys"))


def public_url() -> str:
    return os.environ.get("VTD_PUBLIC_URL", "http://localhost:8000").rstrip("/")


def site_path(pid: str, env: str) -> str:
    return f"/{'live' if env == 'production' else 'staging'}/{pid}/"


def _git(src: Path, *args: str, env: dict | None = None, timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(src), *args], capture_output=True, timeout=timeout, env=env)


def head_sha(src: Path) -> str:
    out = _git(src, "rev-parse", "--verify", "HEAD")
    if out.returncode:
        raise DeliveryError("Dự án chưa có commit nào")
    return out.stdout.decode().strip()


def _public(rel: PurePosixPath) -> bool:
    parts = rel.parts
    return bool(parts) and parts[0] not in PRIVATE_TOP and not any(p.startswith(".") or p == "__pycache__" for p in parts)


def snapshot(src: Path, sha: str, dest: Path, select=None) -> list[str]:
    """Write the files of commit `sha` chosen by `select` (default: the public site) into `dest`."""
    select = select or _public
    if not re.fullmatch(r"[0-9a-f]{7,40}", sha):
        raise DeliveryError("Mã commit không hợp lệ")
    out = _git(src, "archive", "--format=tar", sha)
    if out.returncode:
        raise DeliveryError(f"Không đọc được commit {sha[:7]}")
    files = []
    with tarfile.open(fileobj=io.BytesIO(out.stdout)) as tar:
        for m in tar.getmembers():
            rel = PurePosixPath(m.name)
            if not m.isfile() or rel.is_absolute() or ".." in rel.parts or not select(rel):
                continue
            target = dest / Path(*rel.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(tar.extractfile(m).read())
            files.append(str(rel))
    if select is _public and "index.html" not in files:
        raise DeliveryError("Commit không có index.html")
    return sorted(files)


def deploy(pid: str, src: Path, env: str, sha: str | None = None) -> dict:
    """Publish one commit of the project to staging or production, replacing the previous release atomically."""
    if env not in ENVS:
        raise DeliveryError(f"Môi trường không hợp lệ: {env}")
    sha = sha or head_sha(src)
    base = deploy_root() / pid
    base.mkdir(parents=True, exist_ok=True)
    files = _swap(base, env, lambda d: snapshot(src, sha, d))
    # The backend (api/ only, never its data) goes next to it, outside the published folder.
    backend = _swap(base, f"{env}-app", lambda d: snapshot(src, sha, d, _backend_file))
    stop_backend(pid, env)  # next request starts the new code
    return {"env": env, "sha": sha, "files": len(files), "backend": bool(backend),
            "url": public_url() + site_path(pid, env), "at": time.strftime("%Y-%m-%d %H:%M:%S")}


def _swap(base: Path, name: str, build) -> list[str]:
    """Build a folder next to `base/name` and replace it in one rename, so it is never half-written."""
    tmp = base / f".tmp-{name}-{uuid.uuid4().hex[:8]}"
    old = base / f".old-{name}-{uuid.uuid4().hex[:8]}"
    try:
        tmp.mkdir()
        files = build(tmp)
        with _lock:
            target = base / name
            if target.exists():
                target.rename(old)
            tmp.rename(target)
        return files
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        shutil.rmtree(old, ignore_errors=True)


def site_file(pid: str, env: str, path: str) -> Path | None:
    base = (deploy_root() / pid / env).resolve()
    target = (base / (path or "index.html")).resolve()
    if target.is_dir():
        target = target / "index.html"
    if base not in target.parents or not target.is_file():
        return None
    return target


# ---------------------------------------------------------------- the project's own backend, behind a proxy

_procs: dict[tuple[str, str], tuple[subprocess.Popen, int]] = {}
_proc_lock = threading.Lock()


def _backend_file(rel: PurePosixPath) -> bool:
    parts = rel.parts
    return (len(parts) > 1 and parts[0] == "api" and parts[1] != "data"
            and not any(p.startswith(".") or p == "__pycache__" for p in parts))


def app_dir(pid: str, env: str) -> Path:
    return deploy_root() / pid / f"{env}-app"


def admin_token(pid: str) -> str:
    """Per-project access code for the shop's order admin. Lives on the server only, never in the repo."""
    f = deploy_root() / pid / "admin_token"
    if not f.exists():
        f.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(f, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as fh:
            fh.write(secrets.token_urlsafe(24))
    return f.read_text().strip()


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def stop_backend(pid: str, env: str) -> None:
    with _proc_lock:
        entry = _procs.pop((pid, env), None)
    if entry:
        proc = entry[0]
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def stop_all() -> None:
    for pid, env in list(_procs):
        stop_backend(pid, env)


atexit.register(stop_all)


def ensure_backend(pid: str, env: str) -> int | None:
    """Start the deployed commit's api/server.py on a private port (once), with its data outside the code."""
    with _proc_lock:
        entry = _procs.get((pid, env))
        if entry and entry[0].poll() is None:
            return entry[1]
        app = app_dir(pid, env)
        if not (app / "api" / "server.py").is_file():
            return None
        data = deploy_root() / pid / "data" / env
        data.mkdir(parents=True, exist_ok=True)
        port = _free_port()
        from ai.team import _sandbox_env  # same rules as QA: generated code never sees our secrets
        proc = subprocess.Popen([sys.executable, "api/server.py", "--port", str(port), "--data", str(data)],
                                cwd=app, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                env=_sandbox_env() | {"SHOP_ADMIN_TOKEN": admin_token(pid)})
        for _ in range(100):
            try:
                socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
                _procs[(pid, env)] = (proc, port)
                return port
            except OSError:
                if proc.poll() is not None:
                    break
                time.sleep(0.05)
        proc.kill()
        raise DeliveryError("Backend của dự án không khởi động được")


PASS_HEADERS = ("content-type", "location", "cache-control")


def proxy(pid: str, env: str, method: str, path: str, query: str, body: bytes,
          headers: dict[str, str]) -> tuple[int, dict[str, str], bytes]:
    """Forward /<site>/<pid>/api/... to the project's own backend."""
    if len(body) > MAX_BODY:
        return 413, {"content-type": "application/json"}, b'{"error": "payload too large"}'
    try:
        port = ensure_backend(pid, env)
    except DeliveryError:
        port = 0
    if port is None:
        return 404, {"content-type": "application/json"}, b'{"error": "not found"}'
    if not port:
        return 502, {"content-type": "application/json"}, b'{"error": "backend unavailable"}'
    fwd = {k: v for k, v in headers.items() if k.lower() in ("content-type", "authorization")}
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=15)
    try:
        conn.request(method, "/api/" + path + (f"?{query}" if query else ""), body=body or None, headers=fwd)
        r = conn.getresponse()
        return r.status, {k.lower(): v for k, v in r.getheaders() if k.lower() in PASS_HEADERS}, r.read()
    except (OSError, http.client.HTTPException):
        stop_backend(pid, env)
        return 502, {"content-type": "application/json"}, b'{"error": "backend unavailable"}'
    finally:
        conn.close()


# ---------------------------------------------------------------- push to the client's GitHub

def push(src: Path, repo: str, branch: str, sha: str) -> dict:
    """Push commit `sha` of the project repo to the client's repository. Never force-pushes."""
    if not REPO_RE.match(repo) or ".." in repo:
        raise DeliveryError("Repo phải có dạng chủ-sở-hữu/tên-repo")
    if not BRANCH_RE.match(branch) or ".." in branch or branch.endswith((".lock", "/")):
        raise DeliveryError("Tên nhánh không hợp lệ")
    base = os.environ.get("VTD_GITHUB_URL", "https://github.com").rstrip("/")
    url = f"{base}/{repo}.git"
    token = os.environ.get("VTD_GITHUB_TOKEN", "")
    env = {k: v for k, v in os.environ.items() if not k.startswith(("VTD_GITHUB_TOKEN", "ANTHROPIC"))}
    env["GIT_TERMINAL_PROMPT"] = "0"
    if url.startswith("https://"):
        if not token:
            raise DeliveryError("Chưa cấu hình VTD_GITHUB_TOKEN trên máy chủ, chưa thể đẩy lên GitHub của khách")
        # The token goes through git's environment config, never into argv, the URL, or logs.
        auth = base64.b64encode(f"x-access-token:{token}".encode()).decode()
        env.update({"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "http.extraheader",
                    "GIT_CONFIG_VALUE_0": f"AUTHORIZATION: basic {auth}"})
    out = _git(src, "push", "--porcelain", url, f"{sha}:refs/heads/{branch}", env=env, timeout=120)
    if out.returncode:
        msg = (out.stderr or out.stdout).decode(errors="replace")
        for secret in filter(None, [token, env.get("GIT_CONFIG_VALUE_0", "")]):
            msg = msg.replace(secret, "***")
        hint = " (nhánh bên khách đã có lịch sử khác, cần chọn nhánh mới)" if "rejected" in msg else ""
        raise DeliveryError(f"Đẩy lên {repo} thất bại{hint}: {msg.strip()[-400:]}")
    return {"repo": repo, "branch": branch, "sha": sha, "url": f"{base}/{repo}/tree/{branch}",
            "at": time.strftime("%Y-%m-%d %H:%M:%S")}


# ---------------------------------------------------------------- client message

def outbox_dir() -> Path:
    return Path(os.environ.get("VTD_OUTBOX", ROOT / "workspace" / "outbox"))


def send_email(pid: str, to: str, subject: str, body: str) -> dict:
    """Send through SMTP when it is configured; otherwise save the email to the outbox, unsent."""
    if not EMAIL_RE.match(to):
        raise DeliveryError("Địa chỉ email khách không hợp lệ")
    msg = EmailMessage()
    msg["To"], msg["Subject"] = to, subject.replace("\n", " ")[:200]
    msg["From"] = os.environ.get("VTD_SMTP_FROM", "no-reply@localhost")
    msg.set_content(body)
    host = os.environ.get("VTD_SMTP_HOST")
    at = time.strftime("%Y-%m-%d %H:%M:%S")
    if host:
        try:
            with smtplib.SMTP(host, int(os.environ.get("VTD_SMTP_PORT", "587")), timeout=30) as s:
                s.starttls()
                if os.environ.get("VTD_SMTP_USER"):
                    s.login(os.environ["VTD_SMTP_USER"], os.environ.get("VTD_SMTP_PASSWORD", ""))
                s.send_message(msg)
        except (OSError, smtplib.SMTPException) as e:
            raise DeliveryError(f"Gửi email thất bại: {type(e).__name__}") from e
        return {"channel": "email", "to": to, "subject": msg["Subject"], "at": at, "sent": True}
    folder = outbox_dir()
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{pid}-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:4]}.eml"
    path.write_bytes(bytes(msg))
    return {"channel": "outbox", "to": to, "subject": msg["Subject"], "at": at, "sent": False, "file": path.name}


def email_in(text: str) -> str:
    m = re.search(r"[^@\s<>,;:]+@[^@\s<>,;]+\.[A-Za-z]{2,}", text or "")
    return m.group(0) if m else ""
