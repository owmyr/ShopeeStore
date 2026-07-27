"""Streamlit supervision dashboard.

Run: python -m streamlit run dashboard/app.py
(or via CLI: python __main__.py dashboard)
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
from sqlmodel import select

from core import db
from core.config import PROJECT_ROOT, get_settings
from core.models import AgentLedger

st.set_page_config(page_title="ShopeeStore Supervision", layout="wide")
db.init_db()


def load_ledger() -> pd.DataFrame:
    with db.session_scope() as s:
        rows = list(s.exec(select(AgentLedger).order_by(AgentLedger.started_at.desc())).all())  # type: ignore[attr-defined]
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(
        [
            {
                "started_at (UTC)": r.started_at,
                "agent": r.agent,
                "status": r.status,
                "duration_s": round(r.duration_sec or 0, 1),
                "outputs": r.outputs_path,
                "error": (r.error or "").splitlines()[-1][:120] if r.error else "",
            }
            for r in rows
        ]
    )


def latest_report_dir() -> Path | None:
    reports = get_settings().data_dir / "reports"
    if not reports.exists():
        return None
    dirs = sorted((d for d in reports.iterdir() if (d / "report.json").exists()))
    return dirs[-1] if dirs else None


def start_agent(args: list[str], log_name: str) -> None:
    """Detached background run; output goes to data/<log_name>."""
    log_path = get_settings().data_dir / log_name
    log_file = open(log_path, "ab")  # noqa: SIM115 - must outlive this function
    subprocess.Popen(  # noqa: S603 - fixed argv, no shell
        [sys.executable, "-m", "agents.trend_scout.agent", *args],
        cwd=PROJECT_ROOT,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS,
    )


def brl(cents: float) -> str:
    return f"R$ {cents / 100:,.2f}"


st.title("ShopeeStore - Agent Supervision")

with st.sidebar:
    st.header("Actions")
    if st.button("Run Trend Scout now (full, ~15 min)"):
        start_agent(["--force"], "agent_run_now.log")
        st.success("Started in background. Refresh in a few minutes.")
    if st.button("Dry-run (5 products)"):
        start_agent(["--dry-run", "--force"], "agent_run_now.log")
        st.success("Dry-run started. Refresh in ~1 minute.")
    if st.button("Harvest images now"):
        log_path = get_settings().data_dir / "agent_run_now.log"
        log_file = open(log_path, "ab")  # noqa: SIM115
        subprocess.Popen(  # noqa: S603
            [sys.executable, "-m", "agents.image_harvester.agent", "--force"],
            cwd=PROJECT_ROOT,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS,
        )
        st.success("Harvest started. Refresh in ~1 minute.")
    st.caption("Logs: data/agent_run_now.log")

tab_ledger, tab_trends, tab_gallery = st.tabs(
    ["Agent ledger", "Latest trends", "Image gallery"]
)

with tab_ledger:
    df = load_ledger()
    if df.empty:
        st.info("No agent runs recorded yet.")
    else:
        st.dataframe(df, width="stretch", hide_index=True)

with tab_trends:
    report_dir = latest_report_dir()
    if report_dir is None:
        st.info("No reports yet - run the Trend Scout.")
    else:
        payload = json.loads((report_dir / "report.json").read_text(encoding="utf-8"))
        st.caption(f"Report: {report_dir.name}")

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Printed analyzed", payload.get("printed_count", payload["product_count"]))
        c2.metric("Excluded (plain)", payload.get("excluded_plain_count", 0))
        c3.metric("p25", brl(payload["price_p25_cents"]))
        c4.metric("Median", brl(payload["price_p50_cents"]))
        c5.metric("p75", brl(payload["price_p75_cents"]))

        if payload["theme_counts"]:
            themes = pd.DataFrame(payload["theme_counts"], columns=["theme", "count"])
            st.plotly_chart(
                px.bar(themes.head(15), x="count", y="theme", orientation="h",
                       title="Theme frequency"),
                width="stretch",
            )

        products = pd.DataFrame(payload["products"])
        if not products.empty:
            products["price_brl"] = products["price_cents"] / 100
            st.plotly_chart(
                px.histogram(products, x="price_brl", nbins=30,
                             title="Price distribution (BRL)"),
                width="stretch",
            )
            st.dataframe(
                products[["sold_count", "price_brl", "theme", "title", "url"]],
                width="stretch",
                hide_index=True,
            )

with tab_gallery:
    reference_dir = get_settings().data_dir / "reference"
    report_dir = latest_report_dir()
    if not reference_dir.exists() or not any(reference_dir.rglob("*.jpg")):
        st.info("No reference images yet - run the Image Harvester (sidebar).")
    else:
        meta: dict[int, dict] = {}
        if report_dir is not None:
            payload = json.loads((report_dir / "report.json").read_text(encoding="utf-8"))
            meta = {p["item_id"]: p for p in payload["products"]}

        cards = []
        for img in sorted(reference_dir.rglob("*.jpg")):
            item_id = int(img.stem)
            info = meta.get(item_id, {})
            cards.append(
                {
                    "path": img,
                    "folder": img.parent.name,  # theme slug from folder structure
                    "sold": info.get("sold_count", 0),
                    "theme": info.get("theme") or img.parent.name,
                    "price": info.get("price_cents", 0),
                }
            )
        cards.sort(key=lambda c: c["sold"], reverse=True)

        folders = sorted({c["folder"] for c in cards})
        chosen = st.multiselect("Filter by theme folder", folders, default=folders)
        shown = [c for c in cards if c["folder"] in chosen][:24]
        st.caption(f"{len(shown)} of {len(cards)} printed-shirt references (top by sold)")

        cols = st.columns(4)
        for i, card in enumerate(shown):
            with cols[i % 4]:
                caption = f"{card['folder']} | {card['sold']} sold | {brl(card['price'])}"
                st.image(str(card["path"]), caption=caption, width="stretch")
