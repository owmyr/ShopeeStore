"""Dashboard smoke test (Streamlit AppTest - no browser)."""

import io
import json
import zipfile
from datetime import UTC, datetime

import pytest
from sqlmodel import Session, SQLModel, create_engine

from core import db
from core.models import AgentLedger, StoreLead
from dashboard.pitches import generate_subscriber_delivery_message
from dashboard.supervision import (
    build_dossier_zip,
    get_crm_leads,
    get_ledger_history,
    get_or_generate_theme_card,
    get_weekly_dossier_pdf_path,
    update_lead_crm,
)


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    # Save the original engine to restore it later
    original_engine = getattr(db, "_engine", None)

    # Override the engine used by db.session_scope()
    db._engine = engine

    # Clear streamlit caches
    get_ledger_history.clear()

    with Session(engine) as session:
        yield session

    # Restore the original engine
    db._engine = original_engine


def test_app_runs_without_exceptions(isolated, db_session) -> None:
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file("../dashboard/app.py", default_timeout=60)
    at.run()
    assert not at.exception


def test_build_dossier_zip(isolated) -> None:
    """Verify build_dossier_zip creates a valid ZIP with a CSV and nested images."""
    # Setup mock payload and reference images
    payload = {
        "products": [
            {
                "item_id": 1,
                "theme": "memes",
                "sold_count": 100,
                "price_cents": 2500,
                "title": "A",
                "url": "U",
            }
        ]
    }

    report_dir = isolated / "reports" / "test_report"
    report_dir.mkdir(parents=True)
    (report_dir / "report.json").write_text(json.dumps(payload), encoding="utf-8")

    reference_dir = isolated / "reference"
    memes_dir = reference_dir / "memes"
    memes_dir.mkdir(parents=True)
    (memes_dir / "1.jpg").write_bytes(b"image_content")

    # Call the function
    zip_bytes = build_dossier_zip(str(report_dir))
    assert isinstance(zip_bytes, bytes)

    # Read the ZIP
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        names = zf.namelist()
        assert "commercial_summary.csv" in names
        assert "images/memes/1.jpg" in names

        csv_content = zf.read("commercial_summary.csv").decode("utf-8")
        assert "item_id,theme,sold_count,price_brl,title,url" in csv_content
        assert "1,memes,100,25.0,A,U" in csv_content

        img_content = zf.read("images/memes/1.jpg")
        assert img_content == b"image_content"


def test_get_ledger_history(db_session: Session) -> None:
    db_session.add(
        AgentLedger(
            run_id="run1",
            agent="test_agent",
            started_at=datetime.now(UTC).replace(tzinfo=None),
            status="success",
        )
    )
    db_session.commit()
    history = get_ledger_history()
    assert len(history) == 1
    assert history[0]["agent"] == "test_agent"
    assert history[0]["status"] == "success"


def test_get_crm_leads(db_session: Session) -> None:
    lead = StoreLead(
        shop_id=123,
        shop_name="Test Shop",
        discovered_at=datetime.now(UTC).replace(tzinfo=None),
        status="discovered",
        run_id="run1"
    )
    db_session.add(lead)
    db_session.commit()
    leads = get_crm_leads()
    assert len(leads) == 1
    assert leads[0].shop_name == "Test Shop"


def test_update_lead_crm(db_session: Session) -> None:
    lead = StoreLead(
        shop_id=123,
        shop_name="Test Shop",
        discovered_at=datetime.now(UTC).replace(tzinfo=None),
        status="discovered",
        run_id="run1"
    )
    db_session.add(lead)
    db_session.commit()
    lead_id = lead.id

    assert lead_id is not None
    update_lead_crm(lead_id, "contacted", "Called them", "insta_handle")
    db_session.refresh(lead)

    assert lead.status == "contacted"
    assert lead.notes == "Called them"
    assert lead.instagram == "insta_handle"
    assert lead.last_contacted_at is not None


def test_update_lead_crm_sample_sent(db_session: Session) -> None:
    """Verify sample_sent status sets last_contacted_at and does not overwrite it later."""
    lead = StoreLead(
        shop_id=456,
        shop_name="Sample Shop",
        discovered_at=datetime.now(UTC).replace(tzinfo=None),
        status="discovered",
        run_id="run2",
    )
    db_session.add(lead)
    db_session.commit()
    lead_id = lead.id
    assert lead_id is not None

    # Transition to sample_sent
    update_lead_crm(lead_id, "sample_sent", "Sent anime card")
    db_session.refresh(lead)
    assert lead.status == "sample_sent"
    assert lead.last_contacted_at is not None
    first_contact = lead.last_contacted_at

    # Transition to negotiating: last_contacted_at should not be overwritten
    update_lead_crm(lead_id, "negotiating", "Talking numbers")
    db_session.refresh(lead)
    assert lead.status == "negotiating"
    assert lead.last_contacted_at == first_contact


def test_update_lead_crm_no_timestamp_for_other_statuses(db_session: Session) -> None:
    """Verify non-outreach statuses do not set last_contacted_at."""
    lead = StoreLead(
        shop_id=789,
        shop_name="Quiet Shop",
        discovered_at=datetime.now(UTC).replace(tzinfo=None),
        status="discovered",
        run_id="run3",
    )
    db_session.add(lead)
    db_session.commit()
    lead_id = lead.id
    assert lead_id is not None

    update_lead_crm(lead_id, "rejected", "Not interested")
    db_session.refresh(lead)
    assert lead.status == "rejected"
    assert lead.last_contacted_at is None


def test_get_or_generate_theme_card_empty_slug() -> None:
    """Verify empty or falsy theme slug returns None immediately."""
    assert get_or_generate_theme_card("") is None


def test_get_or_generate_theme_card_no_report(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify missing report directory returns None gracefully."""
    monkeypatch.setattr(
        "dashboard.supervision.get_latest_trend_report",
        lambda: (None, None),
    )
    assert get_or_generate_theme_card("anime", report_dir=None) is None


def test_get_or_generate_theme_card_cached(tmp_path) -> None:
    """Verify cached PNG is returned without invoking generation logic."""
    cards_dir = tmp_path / "cards"
    cards_dir.mkdir(parents=True)
    card_file = cards_dir / "anime.png"
    card_file.write_bytes(b"dummy_png_bytes")

    result = get_or_generate_theme_card("anime", report_dir=tmp_path)
    assert result == card_file


def test_get_or_generate_theme_card_generates_on_demand(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify missing card invokes generate_theme_card on demand."""
    expected_path = tmp_path / "cards" / "geek.png"

    def mock_generate(theme_slug: str, report_dir):
        return expected_path

    monkeypatch.setattr("dashboard.supervision.generate_theme_card", mock_generate)
    result = get_or_generate_theme_card("geek", report_dir=tmp_path)
    assert result == expected_path


def test_get_or_generate_theme_card_handles_exception(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify generation failure returns None instead of raising an unhandled exception."""

    def mock_fail(theme_slug: str, report_dir):
        raise RuntimeError("Browser launch failure")

    monkeypatch.setattr("dashboard.supervision.generate_theme_card", mock_fail)
    result = get_or_generate_theme_card("fail_theme", report_dir=tmp_path)
    assert result is None


def test_app_runs_with_crm_funnel_and_cards(isolated, db_session: Session) -> None:
    """Verify Streamlit AppTest runs cleanly with multi-stage CRM leads and opportunity data."""
    from streamlit.testing.v1 import AppTest

    # Setup report with opportunity metadata
    report_dir = isolated / "reports" / "2026-09-06_run"
    cards_dir = report_dir / "cards"
    cards_dir.mkdir(parents=True)
    (cards_dir / "animes.png").write_bytes(b"card_bytes")

    payload = {
        "products": [],
        "theme_opportunities": {
            "animes": {
                "label": "🌊 Alta Procura • Pouca Concorrência",
                "badge_color": "emerald",
            }
        },
    }
    (report_dir / "report.json").write_text(json.dumps(payload), encoding="utf-8")

    # Add diverse leads across stages
    statuses = [
        "discovered",
        "sample_sent",
        "contacted",
        "engaged",
        "interested",
        "negotiating",
        "subscribed",
        "rejected",
    ]
    for i, st_name in enumerate(statuses, start=100):
        db_session.add(
            StoreLead(
                shop_id=i,
                shop_name=f"Shop {i}",
                discovered_at=datetime.now(UTC).replace(tzinfo=None),
                status=st_name,
                top_theme="animes",
                top_product_title=f"Shirt {i}",
                run_id="run_crm_test",
            )
        )
    db_session.commit()

    at = AppTest.from_file("../dashboard/app.py", default_timeout=60)
    at.run()
    assert not at.exception


def test_generate_subscriber_delivery_message_defaults() -> None:
    """Verify subscriber delivery message contains all key components and default links."""
    lead = StoreLead(
        shop_id=999,
        shop_name="Camisetas do Zé",
        discovered_at=datetime.now(UTC).replace(tzinfo=None),
        status="subscribed",
        run_id="run_sub",
    )
    msg = generate_subscriber_delivery_message(lead)
    assert "Fala Camisetas do Zé! Tudo bem?" in msg
    assert "Aqui é da equipe TrendScout. Seu material da semana já está pronto e liberado:" in msg
    assert (
        "1. Dossiê Executivo da Semana "
        "(PDF anexo abaixo com os rankings e diretrizes de corte);"
        in msg
    )
    assert (
        "2. Seu acesso VIP exclusivo ao portal web com auditoria completa "
        "dos anúncios concorrentes:"
        in msg
    )
    assert "?vip=TS-VIP-2026" in msg
    assert "Qualquer dúvida no planejamento das estampas desta semana, só chamar por aqui." in msg
    assert "Boas vendas na produção!" in msg


def test_generate_subscriber_delivery_message_custom_options() -> None:
    """Verify delivery message handles custom portal URL, edition date, and empty name."""
    lead = StoreLead(
        shop_id=888,
        shop_name="",
        discovered_at=datetime.now(UTC).replace(tzinfo=None),
        status="subscribed",
        run_id="run_sub",
    )
    msg = generate_subscriber_delivery_message(
        lead,
        edition_date="Semana 37",
        portal_url="https://vip.trendscout.com.br",
    )
    assert "Fala Parceiro! Tudo bem?" in msg
    assert "Seu material da semana (Semana 37) já está pronto e liberado:" in msg
    assert "https://vip.trendscout.com.br?vip=TS-VIP-2026" in msg


def test_get_weekly_dossier_pdf_path(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify get_weekly_dossier_pdf_path locates dossier.pdf or returns None."""
    monkeypatch.setattr(
        "dashboard.supervision.get_latest_trend_report",
        lambda: (None, None),
    )
    assert get_weekly_dossier_pdf_path() is None

    # Report exists but no dossier.pdf
    report_dir = tmp_path / "report"
    report_dir.mkdir(parents=True)
    monkeypatch.setattr(
        "dashboard.supervision.get_latest_trend_report",
        lambda: (report_dir, {}),
    )
    assert get_weekly_dossier_pdf_path() is None

    # dossier.pdf exists
    pdf_file = report_dir / "dossier.pdf"
    pdf_file.write_bytes(b"mock pdf content")
    assert get_weekly_dossier_pdf_path() == pdf_file


def test_app_runs_with_subscriber_dispatch_hub(isolated) -> None:
    """Verify Streamlit AppTest renders VIP subscriber cards and action buttons."""
    from streamlit.testing.v1 import AppTest

    # Setup report with dossier
    report_dir = isolated / "reports" / "2026-09-09_run"
    report_dir.mkdir(parents=True)
    (report_dir / "report.json").write_text(json.dumps({"products": []}), encoding="utf-8")
    (report_dir / "dossier.pdf").write_bytes(b"%PDF-1.4 dummy pdf")

    # Clear cached report discovery
    dashboard_supervision = pytest.importorskip("dashboard.supervision")
    dashboard_supervision.get_latest_trend_report.clear()

    # Add a subscribed lead to the isolated database
    with db.session_scope() as session:
        session.add(
            StoreLead(
                shop_id=9999,
                shop_name="VIP Estamparia",
                discovered_at=datetime.now(UTC).replace(tzinfo=None),
                status="subscribed",
                city="Brusque",
                state="SC",
                run_id="run_vip_test",
            )
        )
        session.commit()

    at = AppTest.from_file("../dashboard/app.py", default_timeout=60)
    at.run()
    assert not at.exception
    subheaders = [s.value for s in at.subheader]
    assert any("Despacho Semanal de Entregáveis (Assinantes VIP Ativos)" in sh for sh in subheaders)
    dl_buttons = [db_btn.label for db_btn in at.download_button]
    assert any("Baixar Dossiê Executivo (PDF)" in db_btn for db_btn in dl_buttons)
    text_areas = [ta.value for ta in at.text_area]
    assert any("Fala VIP Estamparia! Tudo bem?" in ta for ta in text_areas)


def test_app_runs_with_no_subscribers_shows_callout(isolated) -> None:
    """Verify empty-state callout appears when no leads are marked as subscribed."""
    from streamlit.testing.v1 import AppTest

    with db.session_scope() as session:
        session.add(
            StoreLead(
                shop_id=5555,
                shop_name="Lead Nao Assinante",
                discovered_at=datetime.now(UTC).replace(tzinfo=None),
                status="discovered",
                run_id="run_non_sub",
            )
        )
        session.commit()

    at = AppTest.from_file("../dashboard/app.py", default_timeout=60)
    at.run()
    assert not at.exception
    infos = [info.value for info in at.info]
    assert any(
        "Nenhum assinante ativo no momento. Quando um lead for marcado como 'subscribed'" in msg
        for msg in infos
    )


