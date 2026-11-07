"""Per-project workspace with least-privilege access.

Each project gets its own folder and git repo under workspace/. Agents get a
handle scoped to their role: devs may write, QA and reporters may only read,
and nobody here can deploy.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

def _frontend_path(rel: str) -> bool:
    return not rel.startswith(("api/", "design/", ".")) and rel.endswith((".html", ".css", ".js", ".svg", ".png", ".jpg", ".webp", ".ico"))


# Least privilege: each role may only write its own part of the project.
ROLE_WRITE_RULES = {
    "designer": lambda rel: rel.startswith("design/"),
    "frontend_dev": _frontend_path,
    "backend_dev": lambda rel: rel.startswith("api/") and not rel.startswith("api/data/"),
}


class PermissionDenied(PermissionError):
    pass


class Workspace:
    def __init__(self, root: Path, project_id: str):
        self.dir = (root / project_id).resolve()
        self.dir.mkdir(parents=True, exist_ok=True)
        if not (self.dir / ".git").exists():
            self._git("init", "-q", "-b", "main")
            (self.dir / ".gitignore").write_text(".vtd/\napi/data/\n__pycache__/\n")

    def _git(self, *args: str) -> str:
        out = subprocess.run(
            ["git", "-c", "user.name=Virtual Tech Dept", "-c", "user.email=bot@vtd.local", *args],
            cwd=self.dir, capture_output=True, text=True, check=True,
        )
        return out.stdout.strip()

    def resolve(self, rel: str) -> Path:
        p = (self.dir / rel).resolve()
        if p != self.dir and self.dir not in p.parents:
            raise PermissionDenied(f"Path escapes workspace: {rel}")
        return p

    def for_role(self, role: str) -> "RoleView":
        return RoleView(self, role)

    def commit(self, message: str) -> str | None:
        self._git("add", "-A")
        if not self._git("status", "--porcelain"):
            return None
        self._git("commit", "-q", "-m", message)
        return self._git("rev-parse", "--short", "HEAD")

    def log(self) -> list[str]:
        try:
            return self._git("log", "--oneline").splitlines()
        except subprocess.CalledProcessError:
            return []


class RoleView:
    def __init__(self, ws: Workspace, role: str):
        self._ws = ws
        self.role = role

    @property
    def dir(self) -> Path:
        return self._ws.dir

    def read(self, rel: str) -> str:
        return self._ws.resolve(rel).read_text(encoding="utf-8")

    def exists(self, rel: str) -> bool:
        return self._ws.resolve(rel).exists()

    def list_files(self) -> list[str]:
        return sorted(
            str(p.relative_to(self._ws.dir))
            for p in self._ws.dir.rglob("*")
            if p.is_file() and ".git" not in p.parts and ".vtd" not in p.parts
        )

    def write(self, rel: str, content: str) -> None:
        p = self._ws.resolve(rel)
        rel = str(p.relative_to(self._ws.dir))
        rule = ROLE_WRITE_RULES.get(self.role)
        if rule is None or not rule(rel):
            raise PermissionDenied(f"Vai trò {self.role} không được ghi {rel}")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
