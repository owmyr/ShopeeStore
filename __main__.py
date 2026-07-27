"""CLI entrypoint for shopee-store.

Usage: python __main__.py {run|run-now|dashboard|schedule|login}
"""

from __future__ import annotations

import argparse
import subprocess
import sys

from core.config import PROJECT_ROOT


def main() -> int:
    parser = argparse.ArgumentParser(prog="shopee-store")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("run", help="run Trend Scout once (skips if run recently)")
    sub.add_parser("run-now", help="force Trend Scout run now")
    sub.add_parser("dashboard", help="launch Streamlit supervision UI")
    sub.add_parser("schedule", help="start weekly scheduler (blocking)")
    sub.add_parser("login", help="one-time Shopee login (opens browser)")
    args = parser.parse_args()

    if args.command in ("run", "run-now"):
        import logging

        logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
        from agents.trend_scout.agent import run_once

        out = run_once(force=args.command == "run-now")
        print(f"report: {out}")
        return 0

    if args.command == "dashboard":
        return subprocess.run(
            [sys.executable, "-m", "streamlit", "run", "dashboard/app.py"],
            cwd=PROJECT_ROOT,
        ).returncode

    if args.command == "schedule":
        from core.scheduler import main as scheduler_main

        return scheduler_main()

    if args.command == "login":
        from agents.trend_scout.scraper import login

        path = login()
        print(f"session saved to {path}")
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
