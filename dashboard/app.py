"""Streamlit supervision dashboard.

Run: python -m streamlit run dashboard/app.py
(or via CLI: python __main__.py dashboard)
"""

from __future__ import annotations

import urllib.parse

import pandas as pd
import plotly.express as px
import streamlit as st

from agents.trend_scout.filter import theme_slug as normalize_theme_slug
from core import db
from core.config import get_settings
from dashboard.pitches import (
    generate_email_pitch,
    generate_instagram_pitch,
    generate_instagram_url,
    generate_shopee_chat_pitch,
    generate_shopee_followup_pitch,
    generate_subscriber_delivery_message,
)
from dashboard.supervision import (
    build_dossier_zip,
    dispatch_shopee_chat_outreach,
    get_crm_leads,
    get_latest_trend_report,
    get_ledger_history,
    get_weekly_dossier_pdf_path,
    get_weekly_dossier_png_path,
    start_background_agent,
    update_lead_crm,
)

st.set_page_config(page_title="ShopeeStore Supervision", layout="wide")
db.init_db()


def brl(cents: float) -> str:
    return f"R$ {cents / 100:,.2f}"


st.title("ShopeeStore - Agent Supervision")

with st.sidebar:
    st.header("Actions")
    if st.button("Run Trend Scout now (full, ~15 min)"):
        start_background_agent("agents.trend_scout.agent", ["--force"], "agent_run_now.log")
        st.success("Started in background. Refresh in a few minutes.")
    if st.button("Dry-run (5 products)"):
        start_background_agent(
            "agents.trend_scout.agent", ["--dry-run", "--force"], "agent_run_now.log"
        )
        st.success("Dry-run started. Refresh in ~1 minute.")
    if st.button("Harvest images now"):
        start_background_agent("agents.image_harvester.agent", ["--force"], "agent_run_now.log")
        st.success("Harvest started. Refresh in ~1 minute.")
    if st.button("Run Lead Scout now"):
        start_background_agent("agents.lead_scout.agent", [], "agent_run_now.log")
        st.success("Lead Scout started. Refresh in a few minutes.")
    st.caption("Logs: data/agent_run_now.log")

tab_ledger, tab_trends, tab_gallery, tab_crm = st.tabs(
    ["Agent ledger", "Latest trends", "Image gallery", "Outreach CRM"]
)

with tab_ledger:
    df_rows = get_ledger_history()
    df = pd.DataFrame(df_rows)
    if df.empty:
        st.info("No agent runs recorded yet.")
    else:
        st.dataframe(df, width="stretch", hide_index=True)

with tab_trends:
    report_dir, payload = get_latest_trend_report()
    if report_dir is None or payload is None:
        st.info("No reports yet - run the Trend Scout.")
    else:
        st.caption(f"Report: {report_dir.name}")

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Printed analyzed", payload.get("printed_count", payload.get("product_count", 0)))
        c2.metric("Excluded (plain)", payload.get("excluded_plain_count", 0))
        c3.metric("p25", brl(payload.get("price_p25_cents", 0)))
        c4.metric("Median", brl(payload.get("price_p50_cents", 0)))
        c5.metric("p75", brl(payload.get("price_p75_cents", 0)))

        if payload.get("theme_counts"):
            themes = pd.DataFrame(payload["theme_counts"], columns=["theme", "count"])
            st.plotly_chart(
                px.bar(
                    themes.head(15), x="count", y="theme", orientation="h", title="Theme frequency"
                ),
                width="stretch",
            )

        products = pd.DataFrame(payload.get("products", []))
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
    report_dir, payload = get_latest_trend_report()

    if report_dir and payload:
        zip_data = build_dossier_zip(str(report_dir))
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
        if payload:
            meta = {p["item_id"]: p for p in payload.get("products", [])}

        cards = []
        for img in sorted(reference_dir.rglob("*.jpg")):
            try:
                item_id = int(img.stem)
            except ValueError:
                continue
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
    leads = get_crm_leads()
    report_dir, payload = get_latest_trend_report()
    theme_opportunities = payload.get("theme_opportunities", {}) if payload else {}

    if not leads:
        st.subheader("🚀 Despacho Semanal de Entregáveis (Assinantes VIP Ativos)")
        st.info(
            "Nenhum assinante ativo no momento. Quando um lead for marcado como 'subscribed', "
            "seus botões de despacho 1-clique aparecerão aqui."
        )
        st.divider()
        st.info(
            "No leads discovered yet. Run the Lead Scout in the sidebar "
            "or run: python __main__.py leads"
        )
    else:
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Total Leads", len(leads))
        c2.metric(
            "Dossiê Enviado",
            len([ld for ld in leads if ld.status in ("sample_sent", "contacted")]),
        )
        c3.metric(
            "Engajados / Resposta",
            len([ld for ld in leads if ld.status in ("engaged", "interested")]),
        )
        c4.metric(
            "Em Negociação",
            len([ld for ld in leads if ld.status == "negotiating"]),
        )
        c5.metric(
            "Assinantes Ativos",
            len([ld for ld in leads if ld.status == "subscribed"]),
        )

        st.divider()
        st.subheader("🚀 Despacho Semanal de Entregáveis (Assinantes VIP Ativos)")
        subscribed_leads = [ld for ld in leads if ld.status == "subscribed"]
        if not subscribed_leads:
            st.info(
                "Nenhum assinante ativo no momento. Quando um lead for marcado como 'subscribed', "
                "seus botões de despacho 1-clique aparecerão aqui."
            )
        else:
            dossier_pdf_path = get_weekly_dossier_pdf_path()
            for sub_lead in subscribed_leads:
                with st.container(border=True):
                    shop_display = sub_lead.shop_name or f"Loja #{sub_lead.shop_id}"
                    loc_parts = [p for p in (sub_lead.city, sub_lead.state) if p]
                    loc_display = " / ".join(loc_parts) if loc_parts else "Brasil"
                    sub_date = (
                        (sub_lead.last_contacted_at or sub_lead.discovered_at).strftime("%d/%m/%Y")
                        if (sub_lead.last_contacted_at or sub_lead.discovered_at)
                        else "Recente"
                    )
                    st.markdown(f"### {shop_display}")
                    st.caption(f"📍 {loc_display} • 📅 Data de assinatura: {sub_date}")

                    delivery_msg = generate_subscriber_delivery_message(sub_lead)
                    phone = getattr(sub_lead, "phone", None)
                    if phone:
                        clean_phone = "".join(c for c in str(phone) if c.isdigit())
                        whatsapp_url = (
                            f"https://wa.me/{clean_phone}?text={urllib.parse.quote(delivery_msg)}"
                        )
                    else:
                        whatsapp_url = f"https://wa.me/?text={urllib.parse.quote(delivery_msg)}"

                    btn_c1, btn_c2 = st.columns([2, 1])
                    btn_c1.link_button(
                        "📲 Abrir WhatsApp com Mensagem de Entrega",
                        whatsapp_url,
                        use_container_width=True,
                    )

                    key_id = sub_lead.id if sub_lead.id is not None else sub_lead.shop_id
                    if dossier_pdf_path and dossier_pdf_path.exists():
                        with open(dossier_pdf_path, "rb") as f:
                            btn_c2.download_button(
                                label="📥 Baixar Dossiê Executivo (PDF)",
                                data=f.read(),
                                file_name=dossier_pdf_path.name,
                                mime="application/pdf",
                                key=f"sub_dl_pdf_{key_id}",
                                use_container_width=True,
                            )
                    else:
                        btn_c2.download_button(
                            label="📥 Baixar Dossiê Executivo (PDF)",
                            data=b"",
                            disabled=True,
                            key=f"sub_dl_pdf_{key_id}",
                            use_container_width=True,
                        )

                    st.text_area(
                        "Mensagem de Entrega",
                        value=delivery_msg,
                        height=140,
                        key=f"sub_msg_{key_id}",
                    )
        st.divider()

        f_cols = st.columns([2, 1, 1, 2])
        status_filter = f_cols[0].multiselect(
            "Filter by status",
            options=[
                "discovered",
                "sample_sent",
                "engaged",
                "negotiating",
                "subscribed",
                "rejected",
            ],
            default=["discovered", "sample_sent", "engaged", "negotiating"],
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

        if report_dir:
            dossier_png_path = report_dir / "dossier.png"
            dossier_pdf_path = report_dir / "dossier.pdf"
            with st.container(border=True):
                d_c1, d_c2, d_c3 = st.columns([1, 1, 2])
                if dossier_png_path.exists():
                    with open(dossier_png_path, "rb") as f:
                        d_c1.download_button(
                            label="📥 Baixar Dossiê Semanal (PNG para Chat)",
                            data=f.read(),
                            file_name=f"dossie_semanal_{report_dir.name}.png",
                            mime="image/png",
                            use_container_width=True,
                            key="crm_top_dossier_png",
                        )
                if dossier_pdf_path.exists():
                    with open(dossier_pdf_path, "rb") as f:
                        d_c2.download_button(
                            label="📄 Baixar Dossiê em PDF",
                            data=f.read(),
                            file_name=f"dossie_semanal_{report_dir.name}.pdf",
                            mime="application/pdf",
                            use_container_width=True,
                            key="crm_top_dossier_pdf",
                        )
                d_c3.caption(
                    "💡 **Estratégia Comercial**: Anexe a imagem do Dossiê Semanal na "
                    "1ª mensagem do Chat da Shopee para demonstrar valor e propor a assinatura."
                )

        with st.container(border=True):
            st.markdown("#### 🤖 Automação de Disparo no Chat da Shopee")
            auto_c1, auto_c2, auto_c3, auto_c4 = st.columns([1.5, 1, 1, 2])
            outreach_dry_run = auto_c2.checkbox(
                "Simulação (--dry-run)", value=True, help="Executa e digita sem enviar"
            )
            outreach_headful = auto_c3.checkbox(
                "Janela Visível", value=True, help="Abre o navegador visível para inspeção"
            )
            discovered_count = len([ld for ld in leads if ld.status == "discovered"])
            batch_target = min(10, discovered_count)
            if auto_c1.button(
                f"🚀 Disparar Lote Seguro ({batch_target} Lojas)",
                use_container_width=True,
                disabled=discovered_count == 0,
            ):
                dispatch_shopee_chat_outreach(
                    limit=10, dry_run=outreach_dry_run, headful=outreach_headful
                )
                st.success(
                    f"Disparo de outreach para {batch_target} lojas iniciado em segundo plano! "
                    "Acompanhe o log ou a tela."
                )
            auto_c4.caption(
                f"📊 **Fila de Prospecção**: **{discovered_count}** lojas disponíveis com status "
                "`discovered`.\nCadência segura: 10 lojas/dia com intervalos de 90s a 180s."
            )

        legacy_status_map = {
            "contacted": "sample_sent",
            "interested": "engaged",
        }

        filtered_leads = [
            ld
            for ld in leads
            if (
                ld.status in status_filter
                or legacy_status_map.get(ld.status, ld.status) in status_filter
            )
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
                theme_display = lead.top_theme or "geral / multitemas"
                st.caption(f"{theme_display} | {lead.top_product_title or 'Sem título'}")

                opp = (
                    theme_opportunities.get(lead.top_theme, {})
                    if (lead.top_theme and isinstance(theme_opportunities, dict))
                    else {}
                )
                if not opp and lead.top_theme and isinstance(theme_opportunities, dict):
                    opp = theme_opportunities.get(normalize_theme_slug(lead.top_theme), {})

                if opp.get("label"):
                    st.caption(f"🎯 Oportunidade: **{opp['label']}**")

                chat_c1, chat_c2 = st.columns([1, 1])
                chat_c1.link_button(
                    "💬 Conversar Manualmente",
                    f"https://shopee.com.br/shop/{lead.shop_id}",
                    use_container_width=True,
                )
                if chat_c2.button(
                    "⚡ Disparar Dossiê (1-Clique)",
                    key=f"auto_send_{lead.id}",
                    use_container_width=True,
                ):
                    dispatch_shopee_chat_outreach(
                        lead_id=lead.id, limit=1, dry_run=False, headful=True
                    )
                    st.success(f"Disparo iniciado para {shop_display}!")

                dossier_png = get_weekly_dossier_png_path()
                if dossier_png and dossier_png.exists():
                    with open(dossier_png, "rb") as f:
                        st.download_button(
                            label="📥 Baixar Dossiê Executivo (PNG para Chat)",
                            data=f.read(),
                            file_name=f"dossie_executivo_{report_dir.name}.png",
                            mime="image/png",
                            key=f"dossier_dl_{lead.id}",
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
                    st.markdown("**1. Envio do Dossiê Semanal (1ª Mensagem no Chat da Shopee)**")
                    opp_label = opp.get("label")
                    st.code(generate_shopee_chat_pitch(lead, opp_label), language="text")
                    st.caption(
                        "💡 Dica: Anexe a imagem do Dossiê Executivo (PNG) "
                        "baixada acima nesta mensagem!"
                    )

                    st.markdown("**2. Follow-up de Fechamento (Quando o Lojista Responde)**")
                    st.code(generate_shopee_followup_pitch(lead), language="text")
                    st.caption(
                        "💡 Objetivo: Apresentar a assinatura mensal para envio no "
                        "canal direto da confecção."
                    )

                    if lead.instagram:
                        st.markdown("**Instagram Direct**")
                        st.code(generate_instagram_pitch(lead), language="text")

                    if lead.email:
                        email_pitch = generate_email_pitch(lead)
                        st.markdown("**Email Corporativo**")
                        st.markdown(f"**Assunto:** {email_pitch['subject']}")
                        st.code(email_pitch["body"], language="text")

                ctrl_cols = st.columns(3)
                status_opts = [
                    "discovered",
                    "sample_sent",
                    "engaged",
                    "negotiating",
                    "subscribed",
                    "rejected",
                ]
                current_status = legacy_status_map.get(lead.status, lead.status)
                status_idx = (
                    status_opts.index(current_status) if current_status in status_opts else 0
                )
                new_status = ctrl_cols[0].selectbox(
                    "Status",
                    status_opts,
                    index=status_idx,
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
                    new_status != current_status
                    or new_notes != (lead.notes or "")
                    or clean_insta != lead.instagram
                ):
                    if lead.id is not None:
                        update_lead_crm(lead.id, new_status, new_notes, clean_insta)
                        st.rerun()

