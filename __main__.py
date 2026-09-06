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
    harvest = sub.add_parser("harvest", help="download top product images")
    harvest.add_argument("--max", type=int, default=50, help="max images (default 50)")
    sub.add_parser("pulse", help="daily spike radar (top 20 scrape + diff)")
    dossier_parser = sub.add_parser("dossier", help="generate executive PDF/HTML dossier")
    dossier_parser.add_argument("--theme", type=str, default=None, help="filter by theme slug")
    dossier_parser.add_argument("--html-only", action="store_true", help="skip PDF export")
    leads_parser = sub.add_parser("leads", help="discover and enrich merchant leads")
    leads_parser.add_argument("--max", type=int, default=50, help="max shops to process")
    leads_parser.add_argument("--no-enrich", action="store_true", help="skip BrasilAPI calls")
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

    if args.command == "harvest":
        import logging

        logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
        from agents.image_harvester.agent import run_once as harvest_once

        out = harvest_once(max_images=args.max)
        print(f"images: {out}")
        return 0

    if args.command == "pulse":
        import logging

        logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
        from agents.pulse.agent import run_once as pulse_once

        out = pulse_once()
        print(f"pulse: {out}")
        return 0

    if args.command == "dossier":
        import logging

        logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
        from agents.dossier.agent import generate_dossier

        out = generate_dossier(theme_slug=args.theme, output_pdf=not args.html_only)
        print(f"dossier generated at: {out}")
        return 0

    if args.command == "leads":
        import logging

        logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
        from agents.lead_scout.agent import run_once as leads_once

        count = leads_once(max_shops=args.max, enrich_cnpj=not args.no_enrich)
        print(f"processed {count} shop leads")
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
