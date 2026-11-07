"""Run the pipeline from the terminal without the web UI.

    python -m ai.cli "Làm landing page cho quán cà phê 'Mộc Coffee'"
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from .orchestrator import run_project

ROOT = Path(__file__).resolve().parent.parent


class PrintSink:
    def __init__(self):
        self.artifacts: dict[str, dict] = {}

    def task(self, pid, stage, status, note=""):
        print(f"  [{stage:<12}] {status:<8} {note}")

    def artifact(self, pid, name, data):
        self.artifacts[name] = data

    def event(self, pid, text):
        print(f"  · {text}")

    def finish(self, pid, status, cost):
        print(f"\nTrạng thái: {status}  |  chi phí: ${cost['spent_usd']:.4f} / ${cost['budget_usd']:.2f}"
              f"  ({cost['calls']} lần gọi model)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("message")
    ap.add_argument("--budget", type=float, default=2.0)
    ap.add_argument("--workspace", type=Path, default=ROOT / "workspace" / "projects")
    args = ap.parse_args()

    pid = time.strftime("cli-%Y%m%d-%H%M%S")
    sink = PrintSink()
    run_project(pid, args.message, sink, args.workspace, args.budget)
    report = sink.artifacts.get("report")
    if report:
        print("\n=== Báo cáo ===")
        print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\nSản phẩm: {args.workspace / pid / 'index.html'}")


if __name__ == "__main__":
    main()
