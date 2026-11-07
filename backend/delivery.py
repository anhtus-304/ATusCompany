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

import base64
import io
import json
import os
import re
import shutil
import smtplib
import subprocess
import tarfile
import threading
import time
import uuid
from email.message import EmailMessage
from pathlib import Path, PurePosixPath
from urllib.parse import parse_qs

ROOT = Path(__file__).resolve().parent.parent
ENVS = ("staging", "production")
# Top-level folders of a project that are not part of the public site.
PRIVATE_TOP = {"api", "design"}
MAX_BODY = 16 * 1024
EMAIL_RE = re.compile(r"^[^@\s<>,;]+@[^@\s<>,;]+\.[^@\s<>,;]+$")
REPO_RE = re.compile(r"^[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}$")
BRANCH_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,99}$")
PATTERNS = {
    "email": re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$"),
    "phone": re.compile(r"^\+?[0-9 .()-]{8,20}$"),
}
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


def snapshot(src: Path, sha: str, dest: Path) -> list[str]:
    """Write the public files of commit `sha` into `dest`."""
    if not re.fullmatch(r"[0-9a-f]{7,40}", sha):
        raise DeliveryError("Mã commit không hợp lệ")
    out = _git(src, "archive", "--format=tar", sha)
    if out.returncode:
        raise DeliveryError(f"Không đọc được commit {sha[:7]}")
    files = []
    with tarfile.open(fileobj=io.BytesIO(out.stdout)) as tar:
        for m in tar.getmembers():
            rel = PurePosixPath(m.name)
            if not m.isfile() or rel.is_absolute() or ".." in rel.parts or not _public(rel):
                continue
            target = dest / Path(*rel.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(tar.extractfile(m).read())
            files.append(str(rel))
    if "index.html" not in files:
        raise DeliveryError("Commit không có index.html")
    return sorted(files)


def deploy(pid: str, src: Path, env: str, sha: str | None = None) -> dict:
    """Publish one commit of the project to staging or production, replacing the previous release atomically."""
    if env not in ENVS:
        raise DeliveryError(f"Môi trường không hợp lệ: {env}")
    sha = sha or head_sha(src)
    base = deploy_root() / pid
    base.mkdir(parents=True, exist_ok=True)
    tmp = base / f".tmp-{env}-{uuid.uuid4().hex[:8]}"
    old = base / f".old-{env}-{uuid.uuid4().hex[:8]}"
    try:
        files = snapshot(src, sha, tmp)
        with _lock:
            target = base / env
            if target.exists():
                target.rename(old)
            tmp.rename(target)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        shutil.rmtree(old, ignore_errors=True)
    return {"env": env, "sha": sha, "files": len(files), "url": public_url() + site_path(pid, env),
            "at": time.strftime("%Y-%m-%d %H:%M:%S")}


def site_file(pid: str, env: str, path: str) -> Path | None:
    base = (deploy_root() / pid / env).resolve()
    target = (base / (path or "index.html")).resolve()
    if target.is_dir():
        target = target / "index.html"
    if base not in target.parents or not target.is_file():
        return None
    return target


# ---------------------------------------------------------------- form posts on deployed sites

def validate(fields: list[dict], data: dict) -> tuple[dict, list[str]]:
    """Same rules as the generated api/server.py."""
    clean, errors = {}, []
    for f in fields:
        value = str(data.get(f["name"], "")).strip()
        if not value:
            if f["required"]:
                errors.append(f"{f['name']}: bắt buộc")
            continue
        if len(value) > f["max_length"]:
            errors.append(f"{f['name']}: tối đa {f['max_length']} ký tự")
            continue
        pattern = PATTERNS.get(f["type"])
        if pattern and not pattern.match(value):
            errors.append(f"{f['name']}: không hợp lệ")
            continue
        clean[f["name"]] = value
    return clean, errors


def submit(pid: str, env: str, endpoint: dict, raw: bytes, content_type: str) -> tuple[int, dict]:
    """Store one form post. Returns (status, payload); payload has "redirect" for HTML form posts."""
    if len(raw) > MAX_BODY:
        return 413, {"error": "payload too large"}
    text = raw.decode("utf-8", errors="replace")
    is_json = "application/json" in (content_type or "")
    try:
        data = json.loads(text or "{}") if is_json else {k: v[0] for k, v in parse_qs(text).items()}
    except json.JSONDecodeError:
        return 400, {"error": "invalid json"}
    if not isinstance(data, dict):
        return 400, {"error": "invalid body"}
    clean, errors = validate([f for f in endpoint.get("fields", [])], data)
    if errors:
        return 400, {"error": "validation", "details": errors}
    store = endpoint["path"].strip("/").replace("/", "_") + ".jsonl"
    folder = deploy_root() / pid / "data" / env  # outside the published site
    folder.mkdir(parents=True, exist_ok=True)
    record = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), **clean}
    with _lock, open(folder / store, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    if is_json:
        return endpoint.get("success_status", 201), {"ok": True}
    return 303, {"redirect": "../?sent=1#sent"}


def submissions(pid: str, env: str) -> int:
    folder = deploy_root() / pid / "data" / env
    return sum(sum(1 for _ in open(f, encoding="utf-8")) for f in folder.glob("*.jsonl")) if folder.is_dir() else 0


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
