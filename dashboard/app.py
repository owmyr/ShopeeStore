"""Streamlit supervision dashboard.

Run: python -m streamlit run dashboard/app.py
(or via CLI: python __main__.py dashboard)
"""

from __future__ import annotations

import io
import json
import subprocess
import sys
import urllib.parse
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.express as px
import streamlit as st
from sqlmodel import select

from agents.lead_scout.pitch import (
    generate_email_pitch,
    generate_instagram_pitch,
    generate_instagram_url,
    generate_shopee_chat_pitch,
)
from core import db
from core.config import PROJECT_ROOT, get_settings
from core.models import AgentLedger, StoreLead

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


def start_agent(module: str, args: list[str], log_name: str) -> None:
    """Detached background run; output goes to data/<log_name>."""
    extra_kwargs: dict[str, Any] = {}
    if sys.platform == "win32":
        extra_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
    else:
        extra_kwargs["start_new_session"] = True

    log_path = get_settings().data_dir / log_name
    with open(log_path, "ab") as log_file:
        subprocess.Popen(  # noqa: S603 - fixed argv, no shell
            [sys.executable, "-m", module, *args],
            cwd=PROJECT_ROOT,
            stdin=subprocess.DEVNULL,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            **extra_kwargs,
        )


def brl(cents: float) -> str:
    return f"R$ {cents / 100:,.2f}"


@st.cache_data(show_spinner="Building ZIP...")
def build_dossier_zip(report_name: str, payload: dict) -> bytes:
    """Build an in-memory ZIP containing the commercial summary CSV and all reference images."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # 1. Add CSV
        products = payload.get("products", [])
        df = pd.DataFrame(products)
        if not df.empty:
            df["price_brl"] = df["price_cents"] / 100
            csv_cols = ["item_id", "theme", "sold_count", "price_brl", "title", "url"]
            available_cols = [c for c in csv_cols if c in df.columns]
            csv_str = df[available_cols].to_csv(index=False)
            zf.writestr("commercial_summary.csv", csv_str)

        # 2. Add images
        reference_dir = get_settings().data_dir / "reference"
        if reference_dir.exists():
            for img in reference_dir.rglob("*.jpg"):
                folder = img.parent.name
                arcname = f"images/{folder}/{img.name}"
                zf.write(img, arcname=arcname)
    return buf.getvalue()


st.title("ShopeeStore - Agent Supervision")

with st.sidebar:
    st.header("Actions")
    if st.button("Run Trend Scout now (full, ~15 min)"):
        start_agent("agents.trend_scout.agent", ["--force"], "agent_run_now.log")
        st.success("Started in background. Refresh in a few minutes.")
    if st.button("Dry-run (5 products)"):
        start_agent("agents.trend_scout.agent", ["--dry-run", "--force"], "agent_run_now.log")
        st.success("Dry-run started. Refresh in ~1 minute.")
    if st.button("Harvest images now"):
        start_agent("agents.image_harvester.agent", ["--force"], "agent_run_now.log")
        st.success("Harvest started. Refresh in ~1 minute.")
    if st.button("Run Lead Scout now"):
        start_agent("agents.lead_scout.agent", [], "agent_run_now.log")
        st.success("Lead Scout started. Refresh in a few minutes.")
    st.caption("Logs: data/agent_run_now.log")

tab_ledger, tab_trends, tab_gallery, tab_crm = st.tabs(
    ["Agent ledger", "Latest trends", "Image gallery", "Outreach CRM"]
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
                px.bar(
                    themes.head(15), x="count", y="theme", orientation="h", title="Theme frequency"
                ),
                width="stretch",
            )

        products = pd.DataFrame(payload["products"])
        if not products.empty:
            products["price_brl"] = products["price_cents"] / 100
            st.plotly_chart(
                px.histogram(products, x="price_brl", nbins=30, title="Price distribution (BRL)"),
                width="stretch",
            )
            st.dataframe(
                products[["sold_count", "price_brl", "theme", "title", "url"]],
                width="stretch",
                hide_index=True,
            )

        if payload.get("theme_velocities"):
            velocities = pd.DataFrame(
                payload["theme_velocities"], columns=["theme", "velocity_per_day"]
            )
            st.plotly_chart(
                px.bar(
                    velocities.head(15),
                    x="velocity_per_day",
                    y="theme",
                    orientation="h",
                    title="Surging Themes (Daily Velocity)",
                ),
                width="stretch",
            )

        if payload.get("breakout_products"):
            breakouts = pd.DataFrame(payload["breakout_products"])
            if "price_cents" in breakouts.columns:
                breakouts["price_brl"] = breakouts["price_cents"] / 100
            st.subheader("Breakout Prints (Fastest Growing)")
            cols = ["title", "theme", "velocity_per_day", "price_brl", "url"]
            available_cols = [c for c in cols if c in breakouts.columns]
            st.dataframe(breakouts[available_cols], width="stretch", hide_index=True)

with tab_gallery:
    reference_dir = get_settings().data_dir / "reference"
    report_dir = latest_report_dir()

    if report_dir:
        payload = json.loads((report_dir / "report.json").read_text(encoding="utf-8"))
        zip_data = build_dossier_zip(report_dir.name, payload)
        st.download_button(
            label="Download Weekly Dossier (.ZIP)",
            data=zip_data,
            file_name=f"dossier_{report_dir.name}.zip",
            mime="application/zip",
        )

        pdf_path = report_dir / "dossier.pdf"
        html_path = report_dir / "dossier.html"
        png_path = report_dir / "dossier.png"

        if pdf_path.exists():
            with open(pdf_path, "rb") as f:
                st.download_button(
                    label="Download Executive Dossier (PDF)",
                    data=f,
                    file_name=f"dossier_{report_dir.name}.pdf",
                    mime="application/pdf",
                )
        if png_path.exists():
            with open(png_path, "rb") as f:
                st.download_button(
                    label="Download Dossiê em Imagem (PNG - Pronto p/ Chat Shopee)",
                    data=f,
                    file_name=f"dossier_{report_dir.name}.png",
                    mime="image/png",
                )
        elif html_path.exists() and not pdf_path.exists():
            with open(html_path, "r", encoding="utf-8") as f:
                st.download_button(
                    label="Download Executive Dossier (HTML)",
                    data=f.read(),
                    file_name=f"dossier_{report_dir.name}.html",
                    mime="text/html",
                )

        st.divider()

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

with tab_crm:
    with db.session_scope() as s:
        leads = list(s.exec(select(StoreLead).order_by(StoreLead.discovered_at.desc())).all())

    if not leads:
        st.info(
            "No leads discovered yet. Run the Lead Scout in the sidebar "
            "or run: python __main__.py leads"
        )
    else:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Leads", len(leads))
        c2.metric("With Instagram", len([ld for ld in leads if ld.instagram]))
        c3.metric("With Corporate Email", len([ld for ld in leads if ld.email]))
        c4.metric(
            "Contacted", len([ld for ld in leads if ld.status in ("contacted", "interested")])
        )

        f_cols = st.columns([2, 1, 1, 2])
        status_filter = f_cols[0].multiselect(
            "Filter by status",
            options=["discovered", "contacted", "interested", "rejected"],
            default=["discovered", "contacted", "interested"],
        )
        has_insta_filter = f_cols[1].selectbox(
            "Has Instagram?",
            options=["All", "Yes", "No"],
            index=0,
        )
        has_email_filter = f_cols[2].selectbox(
            "Has Email?",
            options=["All", "Yes", "No"],
            index=0,
        )
        search_query = f_cols[3].text_input(
            "Search merchant / niche",
            value="",
            placeholder="e.g. Zaroc, street, anime...",
        )

        filtered_leads = [
            ld
            for ld in leads
            if ld.status in status_filter
            and (
                has_insta_filter == "All"
                or (has_insta_filter == "Yes" and bool(ld.instagram))
                or (has_insta_filter == "No" and not ld.instagram)
            )
            and (
                has_email_filter == "All"
                or (has_email_filter == "Yes" and bool(ld.email))
                or (has_email_filter == "No" and not ld.email)
            )
            and (
                not search_query.strip()
                or search_query.strip().lower() in (ld.shop_name or "").lower()
                or search_query.strip().lower() in (ld.top_theme or "").lower()
                or search_query.strip().lower() in (ld.top_product_title or "").lower()
                or search_query.strip().lower() in (ld.city or "").lower()
            )
        ]

        st.caption(f"Showing **{len(filtered_leads)}** of **{len(leads)}** merchant leads")
        for lead in filtered_leads:
            with st.container(border=True):
                shop_display = lead.shop_name or f"Loja #{lead.shop_id}"
                title = shop_display
                if lead.razao_social or lead.nome_fantasia:
                    name_parts = [n for n in (lead.nome_fantasia, lead.razao_social) if n]
                    title += f" ({' / '.join(name_parts)})"
                if lead.city and lead.state:
                    title += f" - {lead.city}/{lead.state}"

                st.subheader(title)
                theme_display = lead.top_theme or "camisetas estampadas"
                st.caption(f"{theme_display} | {lead.top_product_title or 'Sem título'}")

                st.link_button(
                    "💬 Conversar no Chat da Shopee",
                    f"https://shopee.com.br/shop/{lead.shop_id}",
                    use_container_width=True,
                )

                btn_cols = st.columns(3)
                if lead.instagram:
                    btn_cols[0].link_button(
                        f"Abrir Instagram DM (@{lead.instagram})",
                        generate_instagram_url(lead.instagram),
                    )
                else:
                    search_name = lead.shop_name or f"Loja {lead.shop_id}"
                    btn_cols[0].link_button(
                        f"🔍 Buscar '{search_name}' no Instagram",
                        f"https://www.instagram.com/explore/search/keyword/?q={urllib.parse.quote(search_name)}",
                    )

                if lead.email:
                    email_pitch = generate_email_pitch(lead)
                    btn_cols[1].link_button(
                        f"Enviar Email ({lead.email})",
                        email_pitch["mailto_url"],
                    )

                shop_link = lead.shop_url or f"https://shopee.com.br/shop/{lead.shop_id}"
                btn_cols[2].link_button("Ver Loja na Shopee", shop_link)

                with st.expander("Ver Sugestão de Pitch"):
                    st.markdown("**Chat da Shopee (Alcance Imediato)**")
                    st.code(generate_shopee_chat_pitch(lead), language="text")

                    if lead.instagram:
                        st.markdown("**Instagram Direct**")
                        st.code(generate_instagram_pitch(lead), language="text")

                    if lead.email:
                        email_pitch = generate_email_pitch(lead)
                        st.markdown("**Email Corporativo**")
                        st.markdown(f"**Assunto:** {email_pitch['subject']}")
                        st.code(email_pitch["body"], language="text")

                ctrl_cols = st.columns(3)
                status_opts = ["discovered", "contacted", "interested", "rejected"]
                new_status = ctrl_cols[0].selectbox(
                    "Status",
                    status_opts,
                    index=status_opts.index(lead.status) if lead.status in status_opts else 0,
                    key=f"status_{lead.id}",
                )
                new_insta = ctrl_cols[1].text_input(
                    "Instagram (@)",
                    value=lead.instagram or "",
                    key=f"insta_{lead.id}",
                )
                new_notes = ctrl_cols[2].text_input(
                    "Notas / Histórico",
                    value=lead.notes or "",
                    key=f"notes_{lead.id}",
                )

                clean_insta = new_insta.strip().lstrip("@") if new_insta.strip() else None
                if (
                    new_status != lead.status
                    or new_notes != (lead.notes or "")
                    or clean_insta != lead.instagram
                ):
                    with db.session_scope() as s:
                        db_lead = s.get(StoreLead, lead.id)
                        if db_lead:
                            db_lead.status = new_status
                            db_lead.notes = new_notes
                            db_lead.instagram = clean_insta
                            if new_status == "contacted" and not db_lead.last_contacted_at:
                                db_lead.last_contacted_at = datetime.now(UTC).replace(tzinfo=None)
                            s.add(db_lead)
                            s.commit()
                    st.rerun()
