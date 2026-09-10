"""Tests for Track 8: Pack Estruturado de Estampas Reais (Par Duplo & Fichas DTF/Silk).

Why: Ensures reliable generation of high-density print crops (1:1 aspect ratio),
accurate industrial printing specifications (DTF vs Silk, A3/A4/10x10cm, fabric, colors),
and consistent packaging of production zip archives for garment manufacturers.
"""

from __future__ import annotations

import csv
import io
import json
import zipfile
from pathlib import Path

import pytest
from PIL import Image

from agents.image_harvester.art_pack import (
    build_weekly_art_pack,
    crop_print_artwork,
    generate_print_spec,
)


class TestCropPrintArtwork:
    """Test suite for high-density 1:1 graphic chest crop algorithm."""

    def test_crop_square_image(self, tmp_path: Path) -> None:
        """Verify cropping a square image yields an exact 1:1 aspect ratio file."""
        src_path = tmp_path / "mockup_square.jpg"
        dst_path = tmp_path / "cropped_square.jpg"

        # Create dummy 1000x1000 RGB test image
        img = Image.new("RGB", (1000, 1000), (220, 220, 220))
        img.save(src_path, format="JPEG")

        result = crop_print_artwork(src_path, dst_path)

        assert result == dst_path
        assert dst_path.exists()

        with Image.open(dst_path) as cropped:
            assert cropped.format == "JPEG"
            w, h = cropped.size
            assert w == h
            assert w > 0

    def test_crop_rectangular_images(self, tmp_path: Path) -> None:
        """Verify portrait and landscape inputs maintain 1:1 square aspect ratio."""
        # 1. Portrait (800x1200)
        portrait_src = tmp_path / "mockup_portrait.jpg"
        portrait_dst = tmp_path / "cropped_portrait.jpg"
        Image.new("RGB", (800, 1200), (200, 200, 200)).save(portrait_src)

        crop_print_artwork(portrait_src, portrait_dst)
        with Image.open(portrait_dst) as cropped:
            assert cropped.width == cropped.height
            assert cropped.width > 0

        # 2. Landscape (1200x800)
        landscape_src = tmp_path / "mockup_landscape.jpg"
        landscape_dst = tmp_path / "cropped_landscape.jpg"
        Image.new("RGB", (1200, 800), (180, 180, 180)).save(landscape_src)

        crop_print_artwork(landscape_src, landscape_dst)
        with Image.open(landscape_dst) as cropped:
            assert cropped.width == cropped.height
            assert cropped.width > 0

    def test_crop_rgba_image_with_transparency(self, tmp_path: Path) -> None:
        """Verify RGBA inputs with alpha transparency are cleanly flattened to RGB."""
        src_path = tmp_path / "mockup_alpha.png"
        dst_path = tmp_path / "cropped_alpha.jpg"

        rgba_img = Image.new("RGBA", (900, 900), (50, 100, 150, 128))
        rgba_img.save(src_path, format="PNG")

        crop_print_artwork(src_path, dst_path)
        assert dst_path.exists()
        with Image.open(dst_path) as cropped:
            assert cropped.mode == "RGB"
            assert cropped.width == cropped.height


class TestGeneratePrintSpec:
    """Test suite for industrial DTF/Silk fabrication specification engine."""

    def test_streetwear_oversized_print_spec(self) -> None:
        """Verify Streetwear/Oversized shirts receive A3 dimensions and heavy fabric."""
        product = {
            "item_id": 101,
            "title": "Camiseta Streetwear Oversized Graphic Costas Heavy Cotton",
            "price_cents": 6990,
            "velocity_per_day": 24.5,
            "sold_count": 850,
            "url": "https://shopee.com.br/item-101",
        }
        spec = generate_print_spec(product, theme="Streetwear")

        assert spec["item_id"] == 101
        assert "A3" in spec["print_size"]
        assert "Algodão 30.1 Penteado" in spec["fabric"]
        assert "pesado" in spec["fabric"]
        assert "Costas" in spec["print_placement"]
        assert spec["price_brl"] == 69.90
        assert spec["velocity_per_day"] == 24.5
        assert spec["shopee_url"] == "https://shopee.com.br/item-101"
        assert "Preto" in spec["garment_colors"]

    def test_pocket_minimalist_print_spec(self) -> None:
        """Verify pocket and minimalist front graphics receive 10x10cm dimensions."""
        product = {
            "item_id": 102,
            "title": "Camiseta Estampada Bolso Peito Minimalista 100% Algodão",
            "price_cents": 3990,
            "velocity_per_day": 12.0,
            "sold_count": 300,
        }
        spec = generate_print_spec(product, theme="Minimalista")

        assert "10x10" in spec["print_size"]
        assert "Bolso" in spec["print_placement"]
        assert spec["fabric"] == "Algodão 30.1 Penteado, Ribana canelada 2x1"

    def test_technique_recommendation_dtf_vs_silk(self) -> None:
        """Verify complex gradients favor DTF while spot lettering favors Silk-Screen."""
        # 1. Full-color anime gradient -> DTF
        anime_prod = {
            "item_id": 201,
            "title": "Camiseta Anime Cyberpunk Full Color Degradê Realista",
            "price_cents": 4990,
        }
        spec_dtf = generate_print_spec(anime_prod, theme="Anime Geek")
        assert spec_dtf["technique"] == "DTF Têxtil Digital"
        assert "gradientes" in spec_dtf["technique_rationale"]

        # 2. 1-color gospel lettering -> Silk-Screen
        gospel_prod = {
            "item_id": 202,
            "title": "Camiseta Gospel Cristã Frase Fé Silk Screen 1 Cor",
            "price_cents": 3290,
        }
        spec_silk = generate_print_spec(gospel_prod, theme="Gospel Cristã")
        assert spec_silk["technique"] == "Silk-Screen"
        assert "matriz" in spec_silk["technique_rationale"]

    def test_relative_shopee_url_expansion(self) -> None:
        """Verify relative URLs and missing URLs expand into fully-qualified links."""
        prod_relative = {
            "item_id": 301,
            "shop_id": 55,
            "title": "Camiseta Rock Vintage",
            "url": "/Camiseta-Rock-Vintage-i.55.301",
        }
        spec = generate_print_spec(prod_relative, theme="Rock")
        assert spec["shopee_url"].startswith("https://shopee.com.br/Camiseta-Rock-Vintage")

        prod_missing_url = {
            "item_id": 302,
            "shop_id": 77,
            "title": "Camiseta Gym Fit",
            "url": "",
        }
        spec2 = generate_print_spec(prod_missing_url, theme="Gym")
        assert spec2["shopee_url"] == "https://shopee.com.br/product/77/302"


class TestBuildWeeklyArtPack:
    """Test suite for complete weekly production archive generation and mirroring."""

    def test_build_weekly_art_pack_success(self, isolated: Path) -> None:
        """Verify building pack from report.json creates valid ZIP with expected files."""
        report_dir = isolated / "reports" / "20260909T000000Z"
        report_dir.mkdir(parents=True)

        report_payload = {
            "generated_at": "20260909T000000Z",
            "product_count": 3,
            "products": [
                {
                    "item_id": 1001,
                    "shop_id": 10,
                    "title": "Camiseta Streetwear Oversized Graphic Costas",
                    "price_cents": 5990,
                    "sold_count": 600,
                    "velocity_per_day": 20.0,
                    "theme": "streetwear",
                    "is_breakout": True,
                    "url": "https://shopee.com.br/item-1001",
                },
                {
                    "item_id": 1002,
                    "shop_id": 10,
                    "title": "Camiseta Streetwear Skater Acid Wash",
                    "price_cents": 4990,
                    "sold_count": 350,
                    "velocity_per_day": 10.0,
                    "theme": "streetwear",
                    "is_breakout": False,
                    "url": "https://shopee.com.br/item-1002",
                },
                {
                    "item_id": 2001,
                    "shop_id": 20,
                    "title": "Camiseta Anime Geek Neon Cyber",
                    "price_cents": 4500,
                    "sold_count": 420,
                    "velocity_per_day": 15.0,
                    "theme": "anime e geek",
                    "is_breakout": True,
                    "url": "https://shopee.com.br/item-2001",
                },
                {
                    "item_id": 9999,
                    "shop_id": 99,
                    "title": "Camiseta Basica Lisa 100% Algodao",
                    "price_cents": 1990,
                    "sold_count": 900,
                    "velocity_per_day": 30.0,
                    "theme": "lisa",
                    "is_breakout": False,
                    "url": "https://shopee.com.br/item-9999",
                },
            ],
        }
        (report_dir / "report.json").write_text(json.dumps(report_payload), encoding="utf-8")

        # Create dummy reference image for item 1001
        ref_dir = isolated / "reference" / "streetwear"
        ref_dir.mkdir(parents=True)
        img = Image.new("RGB", (800, 800), (30, 30, 30))
        img.save(ref_dir / "1001.jpg", format="JPEG")

        # Execute pack generation with copy_to_web=False to isolate test environment
        zip_path = build_weekly_art_pack(report_dir, copy_to_web=False)

        assert zip_path.exists()
        assert zip_path.name == "pack_estampas_semana.zip"

        # 1. Assert distribution mirrors exist
        latest_pack = isolated / "reports" / "latest_pack.zip"
        assert latest_pack.exists()

        # 2. Inspect ZIP archive structure
        with zipfile.ZipFile(zip_path, "r") as zf:
            namelist = zf.namelist()

            # Root CSV catalog and technician guide
            assert "CATALOGO_GERAL.csv" in namelist
            assert "LEIA-ME_GUIA_DE_ESTAMPARIA.txt" in namelist

            # Niche folders
            assert any("Streetwear" in name for name in namelist)
            assert any("Anime_E_Geek" in name or "Anime" in name for name in namelist)

            # Double-pair and specs present
            assert any("mockup_referencia.jpg" in name for name in namelist)
            assert any("grafismo_recorte.jpg" in name for name in namelist)
            assert any("ficha_tecnica.txt" in name for name in namelist)

            # Ensure plain shirt was excluded
            assert not any("9999" in name for name in namelist)

            # Validate CSV columns and contents
            csv_content = zf.read("CATALOGO_GERAL.csv").decode("utf-8")
            rows = list(csv.DictReader(io.StringIO(csv_content)))
            assert len(rows) == 3
            expected_cols = {
                "item_id",
                "theme",
                "title",
                "price_brl",
                "velocity_per_day",
                "technique",
                "print_size",
                "shopee_url",
            }
            assert expected_cols.issubset(rows[0].keys())

            # Validate ficha_tecnica.txt formatting
            ficha_sample = [n for n in namelist if n.endswith("ficha_tecnica.txt")][0]
            ficha_text = zf.read(ficha_sample).decode("utf-8")
            assert "FICHA TÉCNICA DE ESTAMPARIA & PRODUÇÃO" in ficha_text
            assert "1. ESPECIFICAÇÃO DE ESTAMPA" in ficha_text
            assert "2. BASE TÊXTIL & MODELAGEM RECOMENDADA" in ficha_text
            assert "3. INTELIGÊNCIA COMERCIAL" in ficha_text

    def test_missing_report_json_raises_file_not_found(self, tmp_path: Path) -> None:
        """Verify FileNotFoundError is raised when report.json does not exist."""
        empty_dir = tmp_path / "empty_report"
        empty_dir.mkdir()
        with pytest.raises(FileNotFoundError, match="report.json not found"):
            build_weekly_art_pack(empty_dir)

    def test_build_weekly_art_pack_copy_to_web_behavior(
        self, isolated: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify copy_to_web flag controls mirroring to web public downloads directory.

        Why: Automated tests and internal analytical runs must not accidentally overwrite
        web public assets, whereas production pipelines require synchronization with
        web/public/downloads.
        """
        fake_root = isolated / "fake_project"
        fake_root.mkdir()
        fake_web_downloads = fake_root / "web" / "public" / "downloads"
        monkeypatch.setattr("agents.image_harvester.art_pack.PROJECT_ROOT", fake_root)

        report_dir = isolated / "reports" / "20260909T000000Z"
        report_dir.mkdir(parents=True, exist_ok=True)
        report_payload = {
            "products": [
                {
                    "item_id": 5001,
                    "title": "Camiseta Rock Caveira Estampada",
                    "price_cents": 4990,
                    "velocity_per_day": 12.0,
                    "theme": "rock",
                }
            ]
        }
        (report_dir / "report.json").write_text(json.dumps(report_payload), encoding="utf-8")

        # 1. When copy_to_web=False, downloads directory must not be created or written to
        build_weekly_art_pack(report_dir, copy_to_web=False)
        assert not fake_web_downloads.exists()

        # 2. When copy_to_web=True, downloads directory must receive the mirror zip
        build_weekly_art_pack(report_dir, copy_to_web=True)
        assert (fake_web_downloads / "pack_estampas_semana.zip").exists()
