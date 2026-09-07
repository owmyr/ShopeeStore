"""Tests for Backend Sanitizer & Exporter (core/exporter.py).

Why: Ensures public portal reports are 100% sanitized, free of competitor
identifying data, have valid mutual exclusion in production directives, and
produce optimized WebP/SVG assets.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PIL import Image

from core.exporter import (
    FORBIDDEN_LEAK_KEYS,
    _validate_zero_leakage,
    compute_directives,
    compute_fabric_radar,
    create_svg_placeholder,
    export_client_report,
    format_period_label,
    process_product_image,
)


def _build_synthetic_report_data() -> dict[str, Any]:
    """Helper creating rich mock report data for exporter tests."""
    themes = [
        ("streetwear", 50, 4500.0, 4200),
        ("anime e geek", 40, 3200.0, 2490),
        ("religioso e cristao", 35, 3000.0, 2590),
        ("k-pop", 25, 2100.0, 4390),
        ("pets e animais", 20, 2000.0, 3290),
        ("geek e super-herois", 18, 1800.0, 2690),
        ("musica e bandas", 15, 1200.0, 3490),
        ("nostalgia", 12, 1000.0, 3190),
        ("esportes", 10, 800.0, 2790),
        ("frutas e flores", 8, 700.0, 2890),
        ("rock e musica", 6, 600.0, 3390),
    ]

    products = []
    breakouts = []
    item_counter = 100000

    for theme_name, count, vel, price_c in themes:
        for i in range(count):
            item_id = item_counter + i
            p = {
                "item_id": item_id,
                "shop_id": 999000 + (i % 5),
                "shop_name": f"Competitor Store {i % 5}",
                "cnpj": f"12.345.678/000{i % 9}-00",
                "notes": "Internal competitor analysis note",
                "cookies": "sensitive_session_cookie_xyz",
                "title": (
                    f"Camiseta {theme_name.title()} Oversized Streetwear 100% Algodão "
                    f"30.1 Penteado Estampa DTF Costas Modelo {i}"
                ),
                "url": f"https://shopee.com.br/product-i.{item_id}",
                "price_cents": price_c + (i * 50),
                "sold_count": 500 - (i * 5),
                "rating": 4.8,
                "theme": theme_name,
                "image_url": f"https://down-br.img.susercontent.com/file/mock_{item_id}",
                "velocity_per_day": round(vel / count, 1),
                "is_breakout": i < 2,
            }
            products.append(p)
            if len(breakouts) < 15 and i < 2:
                breakouts.append(p)
        item_counter += 1000

    return {
        "generated_at": "20260906T011030Z",
        "product_count": len(products),
        "printed_count": len(products),
        "excluded_plain_count": 5,
        "price_p25_cents": 2690,
        "price_p50_cents": 3290,
        "price_p75_cents": 4290,
        "theme_counts": [(t[0], t[1]) for t in themes],
        "theme_velocities": [(t[0], t[2]) for t in themes],
        "breakout_products": breakouts,
        "products": products,
    }


def test_format_period_label():
    """Verify period label correctly generates standard Brazilian week format."""
    label = format_period_label("20260906T011030Z")
    assert "Semana 36" in label
    assert "Setembro 2026" in label

    # Test fallback on empty string
    fallback = format_period_label("")
    assert "Semana" in fallback


def test_allowlist_projection_zero_leakage(tmp_path: Path):
    """Verify strictly no private identifiers cross into client_report.json."""
    report_data = _build_synthetic_report_data()
    report_dir = tmp_path / "report_source"
    report_dir.mkdir()
    (report_dir / "report.json").write_text(json.dumps(report_data), encoding="utf-8")

    out_dir = tmp_path / "web_public"
    exported_path = export_client_report(report_dir=report_dir, output_dir=out_dir)

    assert exported_path.exists()
    payload = json.loads(exported_path.read_text(encoding="utf-8"))

    # Recursive check for any forbidden keys
    def check_keys(obj: Any):
        if isinstance(obj, dict):
            for k, v in obj.items():
                assert str(k).lower() not in FORBIDDEN_LEAK_KEYS, f"Leaked forbidden key: {k}"
                check_keys(v)
        elif isinstance(obj, list):
            for item in obj:
                check_keys(item)

    check_keys(payload)

    # Check top-level allowed keys
    allowed_top_keys = {
        "meta",
        "market_overview",
        "niches",
        "breakout_prints",
        "fabric_radar",
        "directives",
    }
    assert set(payload.keys()) == allowed_top_keys


def test_validate_zero_leakage_raises():
    """Verify internal validator raises error when sensitive fields are present."""
    bad_payload = {
        "meta": {"report_id": "test"},
        "seller_info": {"shop_id": 12345, "shop_name": "Leak Store"},
    }
    try:
        _validate_zero_leakage(bad_payload)
        raise AssertionError("Should have raised ValueError on forbidden key")
    except ValueError as exc:
        assert "forbidden key" in str(exc)


def test_directives_strict_mutual_exclusion():
    """Verify to_print and to_pause themes are 100% disjoint with max 3 entries each."""
    niches_data = [
        {
            "theme_id": "streetwear",
            "name": "Streetwear",
            "rank": 1,
            "share_pct": 20.0,
            "daily_velocity": 4500.0,
            "price_p25_brl": 35.0,
            "price_p50_brl": 42.0,
            "price_p75_brl": 55.0,
            "status_key": "high_demand_low_comp",
            "status_label": "Alta Procura",
            "badge_color": "emerald",
        },
        {
            "theme_id": "anime-e-geek",
            "name": "Anime E Geek",
            "rank": 2,
            "share_pct": 18.0,
            "daily_velocity": 3200.0,
            "price_p25_brl": 19.9,
            "price_p50_brl": 24.9,
            "price_p75_brl": 29.9,
            "status_key": "high_comp",
            "status_label": "Guerra de Preços",
            "badge_color": "rose",
        },
        {
            "theme_id": "k-pop",
            "name": "K-Pop",
            "rank": 3,
            "share_pct": 15.0,
            "daily_velocity": 2100.0,
            "price_p25_brl": 38.0,
            "price_p50_brl": 45.0,
            "price_p75_brl": 52.0,
            "status_key": "high_demand_low_comp",
            "status_label": "Alta Procura",
            "badge_color": "emerald",
        },
        {
            "theme_id": "basica",
            "name": "Básica",
            "rank": 4,
            "share_pct": 12.0,
            "daily_velocity": 2000.0,
            "price_p25_brl": 15.0,
            "price_p50_brl": 19.9,
            "price_p75_brl": 24.0,
            "status_key": "high_comp",
            "status_label": "Guerra de Preços",
            "badge_color": "rose",
        },
        {
            "theme_id": "geek-e-super-herois",
            "name": "Geek E Super-Heróis",
            "rank": 5,
            "share_pct": 10.0,
            "daily_velocity": 1800.0,
            "price_p25_brl": 22.0,
            "price_p50_brl": 26.5,
            "price_p75_brl": 32.0,
            "status_key": "high_comp",
            "status_label": "Guerra de Preços",
            "badge_color": "rose",
        },
    ]

    directives = compute_directives(niches_data)
    to_print = directives["to_print"]
    to_pause = directives["to_pause"]

    assert len(to_print) <= 3
    assert len(to_pause) <= 3
    assert len(to_print) > 0
    assert len(to_pause) > 0

    print_ids = {p["theme_id"] for p in to_print}
    pause_ids = {p["theme_id"] for p in to_pause}

    assert not (print_ids & pause_ids), f"Collision detected between {print_ids} and {pause_ids}"


def test_fabric_radar_detection():
    """Verify fabric and construction pattern regex properly detects attributes."""
    sample_products = [
        {"title": "Camiseta Algodão 30.1 Penteado Oversized Streetwear Estampa Costas DTF"},
        {"title": "Kit 3 Camisetas Masculinas Básicas Gola Ribana Canelada"},
        {"title": "Camiseta Feminina Baby Look 100% Algodão Premium"},
    ]
    radar = compute_fabric_radar(sample_products)
    assert len(radar) == 5

    names = {r["name"] for r in radar}
    assert "Algodão 30.1 / Penteado" in names
    assert "Modelagem Oversized / Streetwear" in names
    assert "Kits Promocionais (2 a 5 Peças)" in names
    assert "Estampa Costas / DTF Digital" in names
    assert "Gola Ribana / Canelada" in names

    # Check 30.1 count
    c301 = next(r for r in radar if "30.1" in r["name"])
    assert c301["count"] >= 1


def test_image_resizing_and_svg_fallback(tmp_path: Path):
    """Verify images are resized to max 600x600 WebP and SVGs generated when missing."""
    ref_dir = tmp_path / "reference" / "streetwear"
    ref_dir.mkdir(parents=True)
    large_img_path = ref_dir / "12345.jpg"

    # Create a 1200x800 test image
    img = Image.new("RGB", (1200, 800), color=(73, 109, 137))
    img.save(large_img_path, format="JPEG")

    out_images_dir = tmp_path / "public" / "images" / "prints"

    # Test processing existing image
    rel_url = process_product_image(
        item_id=12345,
        theme="streetwear",
        cdn_url=None,
        ref_dir=tmp_path / "reference",
        output_images_dir=out_images_dir,
    )
    assert rel_url in ("/images/prints/12345.webp", "/images/prints/12345.jpg")

    created_file = out_images_dir / Path(rel_url).name
    assert created_file.exists()
    with Image.open(created_file) as proc_img:
        w, h = proc_img.size
        assert w <= 600
        assert h <= 600

    # Test fallback SVG placeholder
    missing_rel_url = process_product_image(
        item_id=99999,
        theme="unknown",
        cdn_url=None,
        ref_dir=tmp_path / "reference",
        output_images_dir=out_images_dir,
    )
    assert missing_rel_url == "/images/prints/99999.svg"
    svg_file = out_images_dir / "99999.svg"
    assert svg_file.exists()
    assert "<svg" in svg_file.read_text(encoding="utf-8")


def test_create_svg_placeholder(tmp_path: Path):
    """Test SVG placeholder file creation, entity escaping, and truncation."""
    svg_path = tmp_path / "test.svg"
    create_svg_placeholder(svg_path, 'Special "Camiseta" & <Rock>')
    assert svg_path.exists()
    content = svg_path.read_text(encoding="utf-8")
    assert "&amp;" in content
    assert "&lt;" in content
    assert "&gt;" in content
    assert "&quot;" in content

    # Test truncation on long title
    long_svg = tmp_path / "long.svg"
    create_svg_placeholder(long_svg, "A" * 50)
    assert "..." in long_svg.read_text(encoding="utf-8")
