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
    run_parser = sub.add_parser("run", help="run Trend Scout once (skips if run recently)")
    run_parser.add_argument("--dry-run", action="store_true", help="scrape only 5 products")
    run_parser.add_argument("--max", type=int, default=None, help="max products")

    run_now_parser = sub.add_parser("run-now", help="force Trend Scout run now")
    run_now_parser.add_argument("--dry-run", action="store_true", help="scrape only 5 products")
    run_now_parser.add_argument("--max", type=int, default=None, help="max products")

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

    export_parser = sub.add_parser(
        "export-web", help="export sanitized public intelligence for web portal"
    )
    export_parser.add_argument(
        "--report-dir", type=str, default=None, help="path to specific report directory"
    )

    outreach_parser = sub.add_parser(
        "outreach-chat", help="send weekly dossier and outreach messages via Shopee Chat"
    )
    outreach_parser.add_argument(
        "--lead-id", type=int, default=None, help="specific lead ID to message"
    )
    outreach_parser.add_argument("--limit", type=int, default=10, help="max leads to process")
    outreach_parser.add_argument(
        "--dry-run", action="store_true", help="simulate without sending or committing status"
    )
    outreach_parser.add_argument(
        "--headful", action="store_true", default=True, help="run with visible browser window"
    )
    outreach_parser.add_argument(
        "--headless", dest="headful", action="store_false", help="run browser in headless mode"
    )
    outreach_parser.add_argument(
        "--delay-min", type=int, default=90, help="min seconds between messages"
    )
    outreach_parser.add_argument(
        "--delay-max", type=int, default=180, help="max seconds between messages"
    )
    args = parser.parse_args()

    if args.command in ("run", "run-now"):
        import logging

        logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
        from agents.trend_scout.agent import run_once

        out = run_once(force=args.command == "run-now", dry_run=args.dry_run, max_products=args.max)
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

    if args.command == "export-web":
        from pathlib import Path

        from core.exporter import export_client_report

        report_dir = Path(args.report_dir) if args.report_dir else None
        out = export_client_report(report_dir=report_dir)
        print(f"client report exported to: {out}")
        return 0

    if args.command == "outreach-chat":
        import logging

        logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
        from agents.outreach.shopee_chat import send_shopee_outreach_batch

        res = send_shopee_outreach_batch(
            limit=args.limit,
            dry_run=args.dry_run,
            headful=args.headful,
            lead_id=args.lead_id,
            delay_range=(args.delay_min, args.delay_max),
        )
        print(f"outreach result: {res}")
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
