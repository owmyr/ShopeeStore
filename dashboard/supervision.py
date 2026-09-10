"""Streamlit supervision data layer (read models and state commands)."""

import io
import json
import subprocess
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st
from sqlmodel import select

from agents.dossier.agent import generate_theme_card
from core import db
from core.config import PROJECT_ROOT, get_settings
from core.models import AgentLedger, StoreLead


@st.cache_data(ttl=15)
def get_ledger_history(limit: int = 50) -> list[dict[str, Any]]:
    """Fetch recent agent runs as serializable dictionaries."""
    with db.session_scope() as s:
        rows = list(
            s.exec(
                select(AgentLedger).order_by(AgentLedger.started_at.desc()).limit(limit)
            ).all()
        )

    res = []
    for r in rows:
        res.append({
            "started_at (UTC)": r.started_at,
            "agent": r.agent,
            "status": r.status,
            "duration_s": round(r.duration_sec or 0, 1),
            "outputs": r.outputs_path,
            "error": (r.error or "").splitlines()[-1][:120] if r.error else "",
        })
    return res


@st.cache_data(ttl=60)
def get_latest_trend_report() -> tuple[Path | None, dict[str, Any] | None]:
    """Discover latest report folder and parse its payload."""
    reports = get_settings().data_dir / "reports"
    if not reports.exists():
        return None, None
    dirs = sorted((d for d in reports.iterdir() if (d / "report.json").exists()))
    if not dirs:
        return None, None

    report_dir = dirs[-1]
    try:
        payload = json.loads((report_dir / "report.json").read_text(encoding="utf-8"))
        return report_dir, payload
    except Exception:
        return report_dir, None


def get_or_generate_theme_card(theme_slug: str, report_dir: Path | None = None) -> Path | None:
    """Get path to theme card PNG, generating it if needed.

    Why: Allows on-demand card generation for B2B outreach samples without
    pre-generating cards for all themes, falling back gracefully if generation fails.
    """
    if not theme_slug:
        return None
    if report_dir is None:
        report_dir, _ = get_latest_trend_report()
    if not report_dir:
        return None
    cards_dir = report_dir / "cards"
    card_path = cards_dir / f"{theme_slug}.png"
    if card_path.exists():
        return card_path
    try:
        return generate_theme_card(theme_slug, report_dir)
    except Exception:
        return None


def get_crm_leads(status_filter: list[str] | None = None) -> list[StoreLead]:
    """Query store leads from database."""
    with db.session_scope() as s:
        query = select(StoreLead).order_by(StoreLead.discovered_at.desc())
        if status_filter:
            query = query.where(StoreLead.status.in_(status_filter))
        return list(s.exec(query).all())


def update_lead_crm(lead_id: int, status: str, notes: str, instagram: str | None = None) -> None:
    """Update CRM fields for a lead.

    Why: Captures salesperson status transitions, personal notes, and verified Instagram handles,
    recording the initial contact timestamp when advancing to sample_sent or contacted.
    """
    with db.session_scope() as s:
        db_lead = s.get(StoreLead, lead_id)
        if db_lead:
            db_lead.status = status
            db_lead.notes = notes
            if instagram is not None:
                db_lead.instagram = instagram
            if status in ("sample_sent", "contacted") and not db_lead.last_contacted_at:
                db_lead.last_contacted_at = datetime.now(UTC).replace(tzinfo=None)
            s.add(db_lead)
            s.commit()


def start_background_agent(module: str, args: list[str], log_name: str) -> None:
    """Start a detached background agent."""
    extra_kwargs: dict[str, Any] = {}
    if sys.platform == "win32":
        extra_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
    else:
        extra_kwargs["start_new_session"] = True

    log_path = get_settings().data_dir / log_name
    with open(log_path, "ab") as log_file:
        subprocess.Popen(  # noqa: S603
            [sys.executable, "-m", module, *args],
            cwd=PROJECT_ROOT,
            stdin=subprocess.DEVNULL,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            **extra_kwargs,
        )


@st.cache_data(show_spinner="Building ZIP...")
def build_dossier_zip(report_dir_str: str) -> bytes:
    """Build an in-memory ZIP containing the commercial summary CSV and reference images."""
    report_dir = Path(report_dir_str)
    report_json_path = report_dir / "report.json"
    payload = {}
    if report_json_path.exists():
        try:
            payload = json.loads(report_json_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # Add CSV
        products = payload.get("products", [])
        df = pd.DataFrame(products)
        if not df.empty:
            df["price_brl"] = df["price_cents"] / 100
            csv_cols = ["item_id", "theme", "sold_count", "price_brl", "title", "url"]
            available_cols = [c for c in csv_cols if c in df.columns]
            csv_str = df[available_cols].to_csv(index=False)
            zf.writestr("commercial_summary.csv", csv_str)

        # Add images
        reference_dir = get_settings().data_dir / "reference"
        if reference_dir.exists():
            for img in reference_dir.rglob("*.jpg"):
                folder = img.parent.name
                arcname = f"images/{folder}/{img.name}"
                zf.write(img, arcname=arcname)
    return buf.getvalue()


def get_weekly_pack_zip_path() -> Path | None:
    """Locate the weekly print pack ZIP archive across standard export paths.

    Why: Gives callers an authoritative source to locate the generated printable
    matrices and tech specs package for 1-click dispatch to VIP subscribers.
    """
    latest_report_dir, _ = get_latest_trend_report()
    if latest_report_dir:
        report_pack = latest_report_dir / "pack_estampas_semana.zip"
        if report_pack.exists():
            return report_pack

    data_pack = get_settings().data_dir / "reports" / "latest_pack.zip"
    if data_pack.exists():
        return data_pack

    web_pack = PROJECT_ROOT / "web" / "public" / "downloads" / "pack_estampas_semana.zip"
    if web_pack.exists():
        return web_pack

    return None


def get_weekly_dossier_pdf_path() -> Path | None:
    """Locate the weekly executive dossier PDF in the latest report directory.

    Why: Allows dispatch mechanisms and supervision dashboards to access the compiled
    executive intelligence report for subscriber fulfillment.
    """
    latest_report_dir, _ = get_latest_trend_report()
    if latest_report_dir:
        dossier_pdf = latest_report_dir / "dossier.pdf"
        if dossier_pdf.exists():
            return dossier_pdf

    return None

