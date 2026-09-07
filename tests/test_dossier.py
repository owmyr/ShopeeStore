import json
from pathlib import Path
from unittest.mock import patch

from agents.dossier import generate_dossier, generate_theme_card


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


@patch("agents.dossier.agent.sync_playwright")
def test_generate_theme_card_basic(mock_playwright, tmp_path: Path):
    """Test generating theme card HTML and PNG with mocked Playwright."""
    report_data = {
        "generated_at": "20260728T110709Z",
        "product_count": 10,
        "theme_counts": [["streetwear", 5]],
        "theme_velocities": [["streetwear", 150.0]],
        "theme_opportunities": {
            "streetwear": {
                "label": "Alta Procura • Pouca Concorrência",
                "badge_color": "emerald",
            }
        },
        "products": [
            {
                "item_id": 101,
                "title": "Camiseta Streetwear Oversized 1",
                "theme": "streetwear",
                "price_cents": 4990,
                "sold_count": 200,
                "velocity_per_day": 25.5,
                "image_url": "http://example.com/101.jpg",
            },
            {
                "item_id": 102,
                "title": "Camiseta Streetwear Oversized 2",
                "theme": "streetwear",
                "price_cents": 5990,
                "sold_count": 150,
                "velocity_per_day": 18.0,
                "image_url": "http://example.com/102.jpg",
            },
            {
                "item_id": 103,
                "title": "Camiseta Streetwear Graphic 3",
                "theme": "streetwear",
                "price_cents": 3990,
                "sold_count": 100,
                "velocity_per_day": 12.0,
                "image_url": "http://example.com/103.jpg",
            },
        ],
    }

    (tmp_path / "report.json").write_text(json.dumps(report_data))

    mock_p = mock_playwright.return_value.__enter__.return_value
    mock_browser = mock_p.chromium.launch.return_value
    mock_page = mock_browser.new_page.return_value

    png_path = generate_theme_card("streetwear", report_dir=tmp_path)

    assert png_path == tmp_path / "cards" / "streetwear.png"
    assert (tmp_path / "cards" / "streetwear.html").exists()

    html_content = (tmp_path / "cards" / "streetwear.html").read_text(encoding="utf-8")
    assert "RADAR SEMANAL DE VENDAS • CAMISETAS SHOPEE BR" in html_content
    assert "EDIÇÃO SEMANAL" in html_content
    assert "Nicho: Streetwear" in html_content
    assert "Alta Procura • Pouca Concorrência" in html_content
    assert "badge-emerald" in html_content
    assert "Ritmo do nicho: +150 peças/dia • 5 anúncios monitorados" in html_content
    assert "Camiseta Streetwear Oversized 1" in html_content
    assert "+25.5 peças/dia" in html_content
    assert "R$ 49,90" in html_content
    assert "Relatório semanal de inteligência em estamparia" in html_content

    mock_p.chromium.launch.assert_called_once_with(headless=True, channel="chrome")
    mock_page.screenshot.assert_called_once_with(path=str(png_path), type="png")


@patch("agents.dossier.agent.sync_playwright")
def test_generate_theme_card_fallback_breakouts(mock_playwright, tmp_path: Path):
    """Test theme card falls back to breakout products when theme has < 3 items."""
    report_data = {
        "generated_at": "20260728T110709Z",
        "product_count": 10,
        "theme_counts": [["anime", 1]],
        "breakout_products": [
            {
                "item_id": 901,
                "title": "Breakout T-shirt 1",
                "theme": "streetwear",
                "price_cents": 3500,
                "sold_count": 500,
                "velocity_per_day": 50.0,
                "image_url": "http://example.com/901.jpg",
            },
            {
                "item_id": 902,
                "title": "Breakout T-shirt 2",
                "theme": "geek",
                "price_cents": 4500,
                "sold_count": 400,
                "velocity_per_day": 40.0,
                "image_url": "http://example.com/902.jpg",
            },
        ],
        "products": [
            {
                "item_id": 1,
                "title": "Anime Hero T-shirt",
                "theme": "anime",
                "price_cents": 2990,
                "sold_count": 100,
                "velocity_per_day": 10.0,
                "image_url": "http://example.com/1.jpg",
            }
        ],
    }

    (tmp_path / "report.json").write_text(json.dumps(report_data))

    png_path = generate_theme_card("anime", report_dir=tmp_path)
    assert png_path == tmp_path / "cards" / "anime.png"

    html = (tmp_path / "cards" / "anime.html").read_text(encoding="utf-8")
    assert "Anime Hero T-shirt" in html
    assert "Breakout T-shirt 1" in html
    assert "Breakout T-shirt 2" in html


@patch("agents.dossier.agent._fetch_cdn_image", return_value="data:image/jpeg;base64,mockcdn")
@patch("agents.dossier.agent.sync_playwright")
def test_generate_theme_card_image_sources(mock_playwright, mock_cdn, tmp_path: Path):
    """Test resolving local reference image, CDN fallback, and SVG placeholder."""
    ref_dir = tmp_path / "reference" / "gamer"
    ref_dir.mkdir(parents=True, exist_ok=True)
    local_img = ref_dir / "201.jpg"
    local_img.write_bytes(b"dummy image bytes")

    report_data = {
        "generated_at": "20260728T110709Z",
        "product_count": 3,
        "theme_counts": [["gamer", 3]],
        "products": [
            {
                "item_id": 201,
                "title": "Local Image Prod",
                "theme": "gamer",
                "price_cents": 3000,
                "sold_count": 100,
                "velocity_per_day": 10.0,
            },
            {
                "item_id": 202,
                "title": "CDN Image Prod",
                "theme": "gamer",
                "price_cents": 3000,
                "sold_count": 80,
                "velocity_per_day": 8.0,
                "image_url": "http://example.com/202.jpg",
            },
            {
                "item_id": 203,
                "title": "SVG Placeholder Prod",
                "theme": "gamer",
                "price_cents": 3000,
                "sold_count": 50,
                "velocity_per_day": 5.0,
            },
        ],
    }

    (tmp_path / "report.json").write_text(json.dumps(report_data))

    with patch("agents.dossier.agent.get_settings") as mock_settings:
        mock_settings.return_value.data_dir = tmp_path
        generate_theme_card("gamer", report_dir=tmp_path)

    html = (tmp_path / "cards" / "gamer.html").read_text(encoding="utf-8")
    assert "Local Image Prod" in html
    assert "CDN Image Prod" in html
    assert "SVG Placeholder Prod" in html
    # SVG fallback includes svg data URI
    assert "data:image/svg+xml;base64," in html
    # CDN image includes mockcdn
    assert "data:image/jpeg;base64,mockcdn" in html


def test_generate_theme_card_missing_dir(tmp_path: Path):
    """Test FileNotFoundError when report.json does not exist."""
    import pytest

    with pytest.raises(FileNotFoundError):
        generate_theme_card("unknown_theme", report_dir=tmp_path / "nonexistent")


def test_generate_dossier_comprehensive_intelligence(tmp_path: Path):
    """Test full executive dossier with real velocity, macro KPIs, Top 10 themes, and fabrics."""
    report_data = {
        "generated_at": "20260906T011030Z",
        "product_count": 100,
        "printed_count": 100,
        "price_p25_cents": 2500,
        "price_p50_cents": 3500,
        "price_p75_cents": 4500,
        "theme_counts": [
            ["streetwear", 30],
            ["religioso", 25],
            ["anime", 20],
            ["k-pop", 15],
            ["geek", 10],
        ],
        "theme_velocities": [
            ["streetwear", 1200.0],
            ["religioso", 800.0],
            ["anime", 600.0],
            ["k-pop", 500.0],
            ["geek", 300.0],
        ],
        "theme_opportunities": {
            "streetwear": {
                "status_key": "high_demand_low_comp",
                "label": "Alta Procura • Pouca Concorrência",
                "badge_color": "emerald",
            },
            "anime": {
                "status_key": "high_comp",
                "label": "Nicho Muito Disputado (Briga de Preço)",
                "badge_color": "amber",
            },
        },
        "products": [
            {
                "item_id": 1001,
                "title": "Camiseta Oversized Streetwear 100% Algodão 30.1 Penteado Gola Ribana",
                "theme": "streetwear",
                "price_cents": 4990,
                "sold_count": 1500,
                "velocity_per_day": 150.0,
                "url": "https://shopee.com.br/item-1001",
            },
            {
                "item_id": 1002,
                "title": "Camiseta Anime Clássica Estampa Frontal Silk",
                "theme": "anime",
                "price_cents": 2500,
                "sold_count": 800,
                "velocity_per_day": 80.0,
                "url": "https://shopee.com.br/item-1002",
            },
        ],
    }

    (tmp_path / "report.json").write_text(json.dumps(report_data), encoding="utf-8")

    out_path = generate_dossier(report_dir=tmp_path, output_pdf=False)
    assert out_path.name == "dossier.html"
    assert out_path.exists()

    html = out_path.read_text(encoding="utf-8")

    # Header and Meta
    assert "RADAR SEMANAL DE INTELIGÊNCIA EM ESTAMPARIA • SHOPEE BR" in html
    assert "06/09/2026" in html
    assert "20260906T011030Z" in html

    # Macro KPIs
    assert "100" in html  # Listings
    assert "Ritmo do Mercado" in html
    assert "Faturamento Semanal Est." in html
    assert "Preço Mediano Base" in html
    assert "R$ 35,00" in html

    # Top 10 Themes Table & Badges
    assert "Termômetro de Mercado: Ranking dos Top 10 Nichos da Semana" in html
    assert "Streetwear" in html
    assert "Alta Procura • Pouca Concorrência" in html
    assert "Nicho Muito Disputado (Briga de Preço)" in html

    # Modelagem and Fabric Radar
    assert "Radar de Modelagens e Tecidos Vencedores" in html
    assert "Algodão 30.1 / Penteado" in html
    assert "Modelagem Oversized / Streetwear" in html

    # Breakout Products
    assert "As 12 Estampas que Mais Aceleraram em Vendas (Breakouts)" in html
    assert "Camiseta Oversized Streetwear 100% Algodão 30.1" in html
    assert "+150 peças/dia" in html
    assert "R$ 49,90" in html
    assert "https://shopee.com.br/item-1001" in html

    # Strategic Directives
    assert "Diretrizes Táticas de Produção da Semana" in html
    assert "O Que Estampar (Alta Tração &amp; Margem Sadia)" in html or "O Que Estampar" in html
    assert "O Que Pausar / Risco de Margem" in html

    # Monthly Subscription Callout
    assert "CLUBE DE INTELIGÊNCIA VIP • RADAR SEMANAL DE ESTAMPARIA" in html
    assert "R$ 97,00 / mês" in html
    assert "wa.me" in html


