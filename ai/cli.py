"""Run the pipeline from the terminal without the web UI.

    python -m ai.cli "Làm landing page cho quán cà phê 'Mộc Coffee'"
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from .orchestrator import build_project, plan_project

ROOT = Path(__file__).resolve().parent.parent


class PrintSink:
    def __init__(self):
        self.artifacts: dict[str, dict] = {}

    def task(self, pid, stage, status, note=""):
        print(f"  [{stage:<12}] {status:<8} {note}")

    def artifact(self, pid, name, data):
        self.artifacts[name] = data

    def load(self, pid, name):
        return self.artifacts.get(name)

    def event(self, pid, text):
        print(f"  · {text}")

    def finish(self, pid, status, cost):
        print(f"\nTrạng thái: {status}  |  chi phí: ${cost['spent_usd']:.4f} / ${cost['budget_usd']:.2f}"
              f"  ({cost['calls']} lần gọi model)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("message")
    ap.add_argument("--budget", type=float, default=2.0)
    ap.add_argument("--choose", default="ask", help="A/B/C, 'recommended', hoặc 'ask' để hỏi")
    ap.add_argument("--workspace", type=Path, default=ROOT / "workspace" / "projects")
    args = ap.parse_args()

    pid = time.strftime("cli-%Y%m%d-%H%M%S")
    sink = PrintSink()
    if plan_project(pid, args.message, sink, args.budget) != "awaiting_choice":
        return
    proposal = sink.artifacts["proposal"]
    print("\n=== Phương án ===")
    for o in proposal["options"]:
        star = " (khuyên chọn)" if o["id"] == proposal["recommended"] else ""
        print(f"[{o['id']}] {o['name']}{star}: {o['est_days']:g} ngày, {o['est_price_vnd']:,} VND")
        print(f"    {o['summary']}")
        print(f"    + {'; '.join(o['pros'])}\n    - {'; '.join(o['cons'])}")
    print(f"Lý do khuyên: {proposal['reasoning']}")
    choice = args.choose
    if choice == "ask":
        choice = input(f"Chọn phương án [{proposal['recommended']}]: ").strip().upper() or "recommended"
    if choice == "recommended":
        choice = proposal["recommended"]
    print()
    build_project(pid, choice, sink, args.workspace, args.budget)
    report = sink.artifacts.get("report")
    if report:
        print("\n=== Báo cáo ===")
        print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\nSản phẩm: {args.workspace / pid / 'index.html'}")


if __name__ == "__main__":
    main()
