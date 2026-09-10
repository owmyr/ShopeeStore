import json
from pathlib import Path
from unittest.mock import patch

from agents.dossier import generate_dossier
from core.config import get_settings


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
    assert "Shopee #1001" in html

    # Strategic Directives
    assert "Diretrizes Táticas de Produção da Semana" in html
    assert "O Que Estampar (Alta Tração &amp; Margem Sadia)" in html or "O Que Estampar" in html
    assert "O Que Pausar / Risco de Margem" in html

    # Monthly Subscription Callout & Web Portal
    assert "PORTAL WEB" in html
    assert get_settings().portal_display_url in html
    assert "R$ 97,00 / mês" in html
    assert "Assine respondendo no chat" in html



def test_strategic_production_mutual_exclusion(tmp_path: Path):
    """Test that themes in 'to_print' and 'to_pause' are strictly mutually exclusive."""
    report_data = {
        "generated_at": "20260906T011030Z",
        "product_count": 100,
        "printed_count": 100,
        "price_p25_cents": 2500,
        "price_p50_cents": 3500,
        "price_p75_cents": 4500,
        "theme_counts": [
            ["streetwear", 30],
            ["religioso e cristao", 25],
            ["anime e geek", 20],
            ["k-pop", 15],
            ["geek e super-herois", 10],
        ],
        "theme_velocities": [
            ["streetwear", 1200.0],
            ["religioso e cristao", 800.0],
            ["anime e geek", 600.0],
            ["k-pop", 500.0],
            ["geek e super-herois", 300.0],
        ],
        "theme_opportunities": {
            "streetwear": {
                "status_key": "high_demand_low_comp",
                "label": "Alta Procura",
                "badge_color": "emerald",
            },
            "anime e geek": {
                "status_key": "high_comp",
                "label": "Nicho Disputado",
                "badge_color": "amber",
            },
            "religioso e cristao": {
                "status_key": "high_comp",
                "label": "Guerra de Preços",
                "badge_color": "amber",
            },
        },
        "products": [
            {
                "item_id": 1,
                "title": "Camiseta Streetwear",
                "theme": "streetwear",
                "price_cents": 4500,
                "sold_count": 100,
                "velocity_per_day": 20.0,
            },
            {
                "item_id": 2,
                "title": "Camiseta Anime",
                "theme": "anime e geek",
                "price_cents": 2500,
                "sold_count": 100,
                "velocity_per_day": 15.0,
            },
            {
                "item_id": 3,
                "title": "Camiseta Crista",
                "theme": "religioso e cristao",
                "price_cents": 2200,
                "sold_count": 100,
                "velocity_per_day": 12.0,
            },
            {
                "item_id": 4,
                "title": "Camiseta Kpop",
                "theme": "k-pop",
                "price_cents": 4900,
                "sold_count": 100,
                "velocity_per_day": 10.0,
            },
            {
                "item_id": 5,
                "title": "Camiseta Geek",
                "theme": "geek e super-herois",
                "price_cents": 2800,
                "sold_count": 100,
                "velocity_per_day": 8.0,
            },
        ],
    }
    (tmp_path / "report.json").write_text(json.dumps(report_data), encoding="utf-8")

    out_path = generate_dossier(report_dir=tmp_path, output_pdf=False)
    html = out_path.read_text(encoding="utf-8")

    # Streetwear & K-Pop should be in to_print (O Que Estampar)
    # Anime & Religioso should be in to_pause (O Que Pausar)
    assert "Diretrizes Táticas de Produção da Semana" in html
    # Extract to_print and to_pause blocks from HTML
    print_part = html.split("O Que Estampar")[1].split("O Que Pausar")[0]
    pause_part = html.split("O Que Pausar")[1].split("<footer>")[0]

    assert "Streetwear" in print_part
    assert "Streetwear" not in pause_part

    assert "Religioso E Cristao" in pause_part
    assert "Religioso E Cristao" not in print_part

    assert "Anime E Geek" in pause_part
    assert "Anime E Geek" not in print_part


