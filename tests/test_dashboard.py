"""Dashboard smoke test (Streamlit AppTest - no browser)."""

import io
import json
import zipfile
from datetime import UTC, datetime

import pytest
from sqlmodel import Session, SQLModel, create_engine

from core import db
from core.models import AgentLedger, StoreLead
from dashboard.supervision import (
    build_dossier_zip,
    get_crm_leads,
    get_ledger_history,
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

