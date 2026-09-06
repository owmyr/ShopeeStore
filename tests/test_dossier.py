import json
from pathlib import Path
from unittest.mock import patch

from agents.dossier.agent import generate_dossier


def test_generate_dossier_html_only(tmp_path: Path):
    """Test generating dossier HTML without PDF generation."""
    # Create mock report.json
    report_data = {
        "generated_at": "20260728T110709Z",
        "product_count": 100,
        "printed_count": 100,
        "price_p50_cents": 3000,
        "theme_counts": [
            ["streetwear", 50],
            ["basica", 30],
        ],
        "products": [
            {
                "item_id": 1,
                "title": "T-shirt 1",
                "theme": "streetwear",
                "price_cents": 2999,
                "sold_count": 500,
                "url": "http://example.com/1",
            }
        ],
    }

    (tmp_path / "report.json").write_text(json.dumps(report_data))

    # Test generation
    with patch("agents.dossier.agent.get_latest_report_dir", return_value=tmp_path):
        out_path = generate_dossier(report_dir=tmp_path, output_pdf=False)

    assert out_path.name == "dossier.html"
    assert out_path.exists()

    html = out_path.read_text(encoding="utf-8")
    assert "Dossiê Semanal" in html
    assert "streetwear" in html
    assert "T-shirt 1" in html


def test_generate_dossier_with_theme(tmp_path: Path):
    """Test generating dossier HTML filtered by theme."""
    # Create mock report.json
    report_data = {
        "generated_at": "20260728T110709Z",
        "product_count": 100,
        "printed_count": 100,
        "price_p50_cents": 3000,
        "theme_counts": [
            ["streetwear", 50],
            ["basica", 30],
        ],
        "products": [
            {
                "item_id": 1,
                "title": "T-shirt 1",
                "theme": "streetwear",
                "price_cents": 2999,
                "sold_count": 500,
                "url": "http://example.com/1",
            },
            {
                "item_id": 2,
                "title": "T-shirt 2",
                "theme": "basica",
                "price_cents": 2000,
                "sold_count": 100,
                "url": "http://example.com/2",
            },
        ],
    }

    (tmp_path / "report.json").write_text(json.dumps(report_data))

    # Test generation with theme filter
    with patch("agents.dossier.agent.get_latest_report_dir", return_value=tmp_path):
        out_path = generate_dossier(report_dir=tmp_path, theme_slug="streetwear", output_pdf=False)

    assert out_path.name == "dossier_streetwear.html"
    assert out_path.exists()

    html = out_path.read_text(encoding="utf-8")
    assert "Streetwear" in html
    assert "T-shirt 1" in html
    assert "T-shirt 2" not in html


@patch("agents.dossier.agent.sync_playwright")
def test_generate_dossier_pdf(mock_playwright, tmp_path: Path):
    """Test generating dossier PDF (mocks playwright)."""
    # Create mock report.json
    report_data = {
        "generated_at": "20260728T110709Z",
        "product_count": 10,
        "printed_count": 10,
        "price_p50_cents": 3000,
        "theme_counts": [["anime", 10]],
        "products": [],
    }

    (tmp_path / "report.json").write_text(json.dumps(report_data))

    # Mock playwright Context manager
    mock_p = mock_playwright.return_value.__enter__.return_value
    mock_browser = mock_p.chromium.launch.return_value
    mock_page = mock_browser.new_page.return_value

    with patch("agents.dossier.agent.get_latest_report_dir", return_value=tmp_path):
        out_path = generate_dossier(report_dir=tmp_path, output_pdf=True)

    assert out_path.name == "dossier.pdf"

    # Verify Playwright was called correctly
    mock_p.chromium.launch.assert_called_once_with(headless=True)
    mock_page.goto.assert_called_once()
    mock_page.pdf.assert_called_once_with(path=str(out_path), format="A4", print_background=True)
