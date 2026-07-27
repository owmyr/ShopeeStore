"""APScheduler weekly cron + boot self-heal.

Run blocking:  python -m core.scheduler
On start it self-heals: if the last scheduled run is older than 7 days
(e.g. laptop was off at the cron window), it runs immediately, then enters
the weekly schedule (default: Monday 09:00 America/Sao_Paulo).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from agents.image_harvester import agent as image_harvester
from agents.pulse import agent as pulse
from agents.trend_scout import agent as trend_scout
from core.config import get_settings

log = logging.getLogger(__name__)

LAST_RUN_FILE = "scheduler_last_run.txt"
SELF_HEAL_MAX_AGE_DAYS = 7
TZ = "America/Sao_Paulo"


def _mark_last_run() -> None:
    path = get_settings().data_dir / LAST_RUN_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(datetime.now(UTC).isoformat(), encoding="utf-8")


def last_scheduled_run() -> datetime | None:
    path = get_settings().data_dir / LAST_RUN_FILE
    if not path.exists():
        return None
    try:
        return datetime.fromisoformat(path.read_text(encoding="utf-8").strip())
    except ValueError:
        return None


def _job() -> None:
    log.info("scheduled trend scout run starting")
    try:
        trend_scout.run_once()
        _mark_last_run()
    except Exception:
        log.exception("scheduled trend scout run failed")
        return
    try:
        image_harvester.run_once()  # chain: images for the fresh report
    except Exception:
        log.exception("scheduled image harvest failed")


def _pulse_job() -> None:
    log.info("scheduled pulse run starting")
    try:
        pulse.run_once()
    except Exception:
        log.exception("scheduled pulse run failed")


def self_heal(max_age_days: int = SELF_HEAL_MAX_AGE_DAYS) -> bool:
    """Run immediately if the last scheduled run is stale. Returns True if triggered."""
    last = last_scheduled_run()
    if last is None or (datetime.now(UTC) - last) > timedelta(days=max_age_days):
        log.info("self-heal: last run %s - running now", last or "never")
        _job()
        return True
    log.info("self-heal: last run %s ago - schedule is healthy", datetime.now(UTC) - last)
    return False


def build_scheduler() -> BlockingScheduler:
    settings = get_settings()
    scheduler = BlockingScheduler(timezone=TZ)
    scheduler.add_job(
        _job,
        CronTrigger(
            day_of_week=settings.schedule_cron_weekday,
            hour=settings.schedule_cron_hour,
            minute=0,
        ),
        id="trend_scout_weekly",
        name="Trend Scout weekly scrape",
        replace_existing=True,
    )
    scheduler.add_job(
        _pulse_job,
        CronTrigger(hour=settings.schedule_pulse_hour, minute=30),
        id="pulse_daily",
        name="Pulse daily spike radar",
        replace_existing=True,
    )
    return scheduler


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    self_heal()
    settings = get_settings()
    scheduler = build_scheduler()
    log.info(
        "scheduler started: weekly %s %02d:00 %s (Ctrl+C to stop)",
        settings.schedule_cron_weekday,
        settings.schedule_cron_hour,
        TZ,
    )
    try:
        scheduler.start()
    except KeyboardInterrupt:
        log.info("scheduler stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
