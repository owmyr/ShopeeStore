"""Structured real print art pack generation (double-pair assets & DTF/Silk tech sheets).

Why: Textile decorators, print shops, and apparel entrepreneurs need high-fidelity,
isolated graphic cutouts paired with real garment mockups and precise fabrication
specifications (technique, dimensions, fabric base, colors) to rapidly convert
Shopee Brazil best-seller intelligence into production-ready physical t-shirts.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import re
import shutil
import tempfile
import unicodedata
import zipfile
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from agents.image_harvester.downloader import download_image
from agents.trend_scout.filter import is_plain, theme_slug
from agents.trend_scout.prompts import NAO_ESTAMPADA
from core.config import PROJECT_ROOT, get_settings

logger = logging.getLogger(__name__)


def crop_print_artwork(image_path: Path, output_path: Path) -> Path:
    """Crop the primary print graphic from a garment mockup into a 1:1 high-density artwork.

    Why: Apparel decorators and digital textile printers (DTF / Silk-Screen) require
    isolated artwork free from distracting mannequin backgrounds, neck ribs, collars,
    and sleeves so that graphic files can be directly ingested by RIP software,
    color separation tools, or automated vectorizers without manual retouching.

    Args:
        image_path: Filesystem path to the source mockup image.
        output_path: Destination path where the cropped 1:1 square artwork will be saved.

    Returns:
        The destination Path containing the high-density cropped artwork.
    """
    image_path = Path(image_path)
    output_path = Path(output_path)

    with Image.open(image_path) as img:
        # Convert paletted, alpha, or CMYK buffers into standard RGB on white canvas
        # to ensure universal compatibility with textile RIP software and avoid JPEG artifacts.
        if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
            rgba = img.convert("RGBA")
            canvas = Image.new("RGB", rgba.size, (255, 255, 255))
            canvas.paste(rgba, mask=rgba.split()[3])
            working_img = canvas
        elif img.mode != "RGB":
            working_img = img.convert("RGB")
        else:
            working_img = img.copy()

    w, h = working_img.size

    # Isolate the central graphic zone: horizontal 15% to 85%, vertical 20% to 75%.
    # This intentionally avoids the collar/ribana (top 0-20%), lateral sleeves/arms (outer 15%),
    # and bottom waistline hem (bottom 75-100%).
    w_min = int(0.15 * w)
    w_max = int(0.85 * w)
    h_min = int(0.20 * h)
    h_max = int(0.75 * h)

    avail_w = max(1, w_max - w_min)
    avail_h = max(1, h_max - h_min)
    side = max(1, min(avail_w, avail_h, w, h))

    # Center the square crop box inside the target chest zone
    cx = (w_min + w_max) // 2
    cy = (h_min + h_max) // 2

    left = cx - side // 2
    top = cy - side // 2
    right = left + side
    bottom = top + side

    # Clamp bounds strictly within image dimensions while maintaining 1:1 aspect ratio
    if left < 0:
        right += -left
        left = 0
    if right > w:
        shift = right - w
        left = max(0, left - shift)
        right = w
    if top < 0:
        bottom += -top
        top = 0
    if bottom > h:
        shift = bottom - h
        top = max(0, top - shift)
        bottom = h

    final_side = min(right - left, bottom - top)
    right = left + final_side
    bottom = top + final_side

    cropped = working_img.crop((left, top, right, bottom))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    # Save with quality=85 and optimize=True for production fidelity and lightweight downloads
    cropped.save(output_path, format="JPEG", quality=85, optimize=True)
    return output_path


def generate_print_spec(product: dict[str, Any], theme: str) -> dict[str, Any]:
    """Generate industrial print and fabrication specifications for a top-performing shirt.

    Why: Commercial confectioners and screen printers require deterministic manufacturing
    parameters (recommended technique, real physical dimensions, fabric construction,
    and garment base colors) aligned with current marketplace demand to prevent costly
    shop-floor misprints and streamline factory quoting.

    Args:
        product: Raw product listing dictionary containing title, price, velocity, etc.
        theme: Assigned market theme or niche classification.

    Returns:
        Dictionary containing technical fabrication directives and commercial metrics.
    """
    item_id = int(product.get("item_id") or 0)
    title = str(product.get("title") or "").strip()
    title_lower = title.lower()
    theme_str = (theme or str(product.get("theme") or "Geral")).strip()
    theme_lower = theme_str.lower()

    # 1. Dimensions and Placement
    # Streetwear and oversized styles mandate large format prints (A3: 29.7x42cm) across
    # front chests or upper backs, while pocket prints require localized 10x10cm transfers.
    is_a3 = any(
        kw in title_lower
        for kw in (
            "costas",
            "costa",
            "oversized",
            "streetwear",
            "full print",
            "maxi",
            "a3",
            "costas grande",
        )
    ) or any(kw in theme_lower for kw in ("streetwear", "oversized"))

    is_pocket = any(
        kw in title_lower
        for kw in (
            "bolso",
            "pocket",
            "peito lateral",
            "discreta",
            "pequena",
            "logo peito",
            "minimalista",
        )
    ) or "minimalista" in theme_lower

    if is_a3 and not is_pocket:
        print_size = "A3: 29.7x42cm"
        print_size_label = "A3 (29.7 x 42.0 cm)"
        print_placement = "Costas / Oversized Frontal Amplo"
    elif is_pocket:
        print_size = "10x10cm"
        print_size_label = "10x10 cm"
        print_placement = "Bolso / Peito Lateral Frontal"
    else:
        print_size = "A4: 21x29.7cm"
        print_size_label = "A4 (21.0 x 29.7 cm)"
        print_placement = "Peito Central Padrão"

    # 2. Print Technique Recommendation
    # High-color count, photo-realism, and tonal gradients favor DTF Têxtil Digital
    # (no setup plates, photographic fidelity), whereas 1-3 flat spot colors and lettering
    # are significantly more cost-effective via Silk-Screen (plastisol/water-based).
    dtf_keywords = (
        "dtf",
        "degradê",
        "degrade",
        "foto",
        "fotografica",
        "fotográfica",
        "realista",
        "full color",
        "full-color",
        "colorida",
        "colorido",
        "ilustracao",
        "ilustração",
        "anime",
        "geek",
        "gamer",
        "games",
        "k-pop",
        "kpop",
        "pets",
        "animais",
        "paisagem",
    )
    silk_keywords = (
        "silk",
        "silkscreen",
        "silk-screen",
        "1 cor",
        "2 cores",
        "monocromatica",
        "monocromática",
        "frase",
        "lettering",
        "tipografia",
        "cristã",
        "cristao",
        "gospel",
        "country",
        "agro",
    )

    matches_dtf = any(kw in title_lower for kw in dtf_keywords) or any(
        kw in theme_lower for kw in ("anime", "geek", "k-pop", "pets")
    )
    matches_silk = any(kw in title_lower for kw in silk_keywords) or any(
        kw in theme_lower for kw in ("gospel", "crist", "country", "agro")
    )

    if matches_dtf:
        technique = "DTF Têxtil Digital"
        technique_rationale = (
            "Recomendado para gradientes contínuos, policromia fotográfica, microdetalhes "
            "e tiragens sob demanda sem matriz serigráfica."
        )
    elif matches_silk:
        technique = "Silk-Screen"
        technique_rationale = (
            "Recomendado para 1 a 3 cores sólidas chapadas, alta tiragem com economia de escala "
            "e baixo custo unitário de matriz."
        )
    else:
        technique = "DTF Têxtil Digital"
        technique_rationale = (
            "Recomendado para impressão digital sob demanda sem necessidade de matriz serigráfica."
        )

    # 3. Fabric Specification
    # Penteado 30.1 with 2x1 ribana represents the gold-standard baseline for direct-to-garment
    # and DTF durability, upgraded to heavyweight 180g/m² for streetwear/oversized cuts.
    if "oversized" in title_lower or "streetwear" in theme_lower:
        fabric = "Algodão 30.1 Penteado pesado (180g/m²), Ribana canelada 2x1"
    else:
        fabric = "Algodão 30.1 Penteado, Ribana canelada 2x1"

    garment_colors = ["Preto", "Off-White", "Chumbo", "Areia"]

    # 4. Commercial & Audit Metadata
    shopee_url = str(product.get("url") or "").strip()
    if shopee_url and not shopee_url.startswith("http"):
        prefix = "https://shopee.com.br"
        shopee_url = f"{prefix}{shopee_url if shopee_url.startswith('/') else '/' + shopee_url}"
    if not shopee_url and item_id:
        shop_id = product.get("shop_id", 0)
        shopee_url = f"https://shopee.com.br/product/{shop_id}/{item_id}"

    price_cents = product.get("price_cents")
    if price_cents is not None:
        price_brl = round(float(price_cents) / 100.0, 2)
    else:
        price_brl = round(float(product.get("price_brl") or 0.0), 2)

    velocity_per_day = round(float(product.get("velocity_per_day") or 0.0), 1)
    sold_count = int(product.get("sold_count") or 0)

    return {
        "item_id": item_id,
        "theme": theme_str,
        "title": title,
        "price_brl": price_brl,
        "velocity_per_day": velocity_per_day,
        "sold_count": sold_count,
        "technique": technique,
        "technique_rationale": technique_rationale,
        "print_size": print_size,
        "print_size_label": print_size_label,
        "print_placement": print_placement,
        "fabric": fabric,
        "garment_colors": garment_colors,
        "shopee_url": shopee_url,
    }


def _clean_niche_slug(theme_name: str) -> str:
    """Normalize raw theme strings into safe, readable directory names."""
    normalized = unicodedata.normalize("NFKD", theme_name)
    ascii_theme = "".join(c for c in normalized if not unicodedata.combining(c))
    cleaned = re.sub(r"[^\w\s-]", "", ascii_theme).strip()
    words = [w.capitalize() for w in re.split(r"[\s_-]+", cleaned) if w]
    return "_".join(words) if words else "Geral"


def _format_ficha_tecnica(spec: dict[str, Any]) -> str:
    """Format technical specification dictionary into a clean industrial text sheet."""
    colors_str = ", ".join(spec.get("garment_colors", ["Preto", "Off-White", "Chumbo", "Areia"]))
    return (
        "================================================================================\n"
        "FICHA TÉCNICA DE ESTAMPARIA & PRODUÇÃO - TREND SCOUT BR\n"
        "================================================================================\n"
        f"PRODUTO: {spec.get('title')}\n"
        f"ID DO ITEM: {spec.get('item_id')}\n"
        f"NICHO / TEMA: {spec.get('theme')}\n"
        f"LINK SHOPEE AUDITORIA: {spec.get('shopee_url')}\n"
        "\n"
        "1. ESPECIFICAÇÃO DE ESTAMPA\n"
        "--------------------------------------------------------------------------------\n"
        f"- Dimensão Sugerida: {spec.get('print_size_label', spec.get('print_size'))}\n"
        f"- Enquadramento / Posição: {spec.get('print_placement')}\n"
        f"- Técnica Recomendada: {spec.get('technique')}\n"
        f"- Justificativa Técnica: {spec.get('technique_rationale')}\n"
        "- Arquivo de Grafismo: grafismo_recorte.jpg (Recorte 1:1 de alta densidade)\n"
        "- Mockup de Referência: mockup_referencia.jpg (Visão completa da peça)\n"
        "\n"
        "2. BASE TÊXTIL & MODELAGEM RECOMENDADA\n"
        "--------------------------------------------------------------------------------\n"
        f"- Tecido: {spec.get('fabric')}\n"
        "- Gola: Ribana Canelada 2x1 (largura 2.5cm a 3.0cm)\n"
        f"- Cores de Peça Recomendadas: {colors_str}\n"
        "\n"
        "3. INTELIGÊNCIA COMERCIAL (SHOPEE BR)\n"
        "--------------------------------------------------------------------------------\n"
        f"- Preço Praticado no Mercado: R$ {spec.get('price_brl', 0.0):.2f}\n"
        f"- Velocidade Estimada: {spec.get('velocity_per_day', 0.0)} peças/dia\n"
        f"- Total Unidades Vendidas: {spec.get('sold_count', 0)}\n"
        "\n"
        "================================================================================\n"
        "Instruções para o estampador: Utilize 'grafismo_recorte.jpg' calibrado a 300 DPI\n"
        "na dimensão sugerida acima. Para Silk-Screen, utilize o grafismo para separação\n"
        "de cores em 1 a 3 matrizes. Para DTF, ripe diretamente com perfil CMYK + W.\n"
        "================================================================================\n"
    )


def _generate_technician_guide() -> str:
    """Generate the root instruction manual for workshop operators and print masters."""
    return (
        "================================================================================\n"
        "GUIA DE ESTAMPARIA & PRODUÇÃO INDUSTRIAL - PACK SEMANAL DE ESTAMPAS REAIS\n"
        "Trend Scout BR - Inteligência de Mercado para Moda Camiseteria\n"
        "================================================================================\n"
        "\n"
        "Prezado operador e confeccionista,\n"
        "\n"
        "Este pacote contém a seleção estruturada das estampas reais de maior velocidade\n"
        "e aceleração (breakout) capturadas no mercado da Shopee Brasil nesta semana.\n"
        "\n"
        "1. ESTRUTURA DO PACOTE ('PAR DUPLO')\n"
        "--------------------------------------------------------------------------------\n"
        "Cada pasta de nicho/produto contém o Par Duplo de arquivos visuais:\n"
        "  - 'mockup_referencia.jpg': Visualização completa da camiseta para conferência\n"
        "    de caimento, proporção e posicionamento em relação à gola e barra.\n"
        "  - 'grafismo_recorte.jpg': Recorte 1:1 em altíssima resolução focado exclusivamente\n"
        "    na arte da estampa, sem interferência de golas, mangas ou fundos.\n"
        "  - 'ficha_tecnica.txt': Parâmetros de produção com dimensões, tecidos e técnica.\n"
        "\n"
        "2. DIRETRIZES DE APLICAÇÃO DTF (DIRECT TO FILM)\n"
        "--------------------------------------------------------------------------------\n"
        "  - Resolução de Entrada: Importar o 'grafismo_recorte.jpg' no RIP a 300 DPI.\n"
        "  - Perfil de Impressão: CMYK com base de Branco Duplo (W+CMYK).\n"
        "  - Poliamida: Grão médio em malha de algodão 30.1; grão fino em poliamida/dry.\n"
        "  - Parâmetros de Prensa Térmica:\n"
        "      * 160°C por 15 segundos (pressão média-alta: 4 a 5 bar).\n"
        "      * Retirada do liner (película) a frio ou morno.\n"
        "      * Reprensagem de acabamento com folha de teflon por 5 segundos.\n"
        "\n"
        "3. DIRETRIZES DE APLICAÇÃO SILK-SCREEN (SERIGRAFIA)\n"
        "--------------------------------------------------------------------------------\n"
        "  - Telas Recomendadas: Poliéster 77 a 120 fios conforme detalhe dos traços.\n"
        "  - Tintas: Plastisol para toque leve e alta cobertura em tecidos escuros;\n"
        "    ou Base D'água para toque zero em malhas claras.\n"
        "  - Curagem: Estufa a 160°C por 2 a 3 minutos para fixação total.\n"
        "\n"
        "4. AUDITORIA COMERCIAL\n"
        "--------------------------------------------------------------------------------\n"
        "Consulte o arquivo 'CATALOGO_GERAL.csv' na raiz para checar links diretos de\n"
        "concorrentes, preços praticados e volumes de venda diários.\n"
        "================================================================================\n"
    )


def _resolve_or_fetch_product_image(
    product: dict[str, Any],
    theme: str,
    temp_dir: Path,
) -> Path | None:
    """Resolve product image from local reference library, CDN, or synthetic fallback."""
    item_id = int(product.get("item_id") or 0)
    data_dir = get_settings().data_dir
    ref_dir = data_dir / "reference"
    t_slug = theme_slug(theme)

    candidates = [
        ref_dir / t_slug / f"{item_id}.jpg",
        ref_dir / theme / f"{item_id}.jpg",
        ref_dir / "sem-tema" / f"{item_id}.jpg",
    ]
    for c in candidates:
        if c.exists():
            return c

    # Attempt download from CDN if URL exists
    image_url = product.get("image_url")
    if image_url:
        dl_dest = temp_dir / "downloads" / f"{item_id}.jpg"
        if download_image(image_url, dl_dest):
            return dl_dest

    # Offline/test synthetic fallback generator
    placeholder = temp_dir / "placeholders" / f"{item_id}.jpg"
    placeholder.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (800, 800), (245, 245, 245))
    draw = ImageDraw.Draw(img)
    # T-shirt chest graphic shape
    draw.rectangle([160, 180, 640, 620], fill=(30, 41, 59), outline=(15, 23, 42), width=4)
    draw.text((200, 380), f"ESTAMPA #{item_id}", fill=(255, 255, 255))
    img.save(placeholder, format="JPEG", quality=85, optimize=True)
    return placeholder


def build_weekly_art_pack(
    report_dir: Path,
    output_zip_path: Path | None = None,
    *,
    max_themes: int = 10,
    max_items_per_theme: int = 2,
    copy_to_web: bool = True,
) -> Path:
    """Build an organized production ZIP archive with mockups, 1:1 crops, and tech sheets.

    Why: Print shops, apparel brand creators, and DTF technicians require an immediately
    actionable weekly package containing visual mockups, cropped production-ready graphics,
    standardized manufacturing spec sheets, and a master catalog to produce the highest-velocity
    commercial shirt designs found on Shopee BR. Capping to top themes and items keeps the download
    lightweight (~3-5MB) for web delivery.

    Args:
        report_dir: Path to directory containing report.json.
        output_zip_path: Optional explicit path for the output zip file.
        max_themes: Maximum top market themes to include in the pack (default: 10).
        max_items_per_theme: Maximum products to package per niche folder (default: 2).
        copy_to_web: Whether to mirror the archive to web/public/downloads for web deployment.

    Returns:
        Path to the generated zip archive.
    """
    report_dir = Path(report_dir)
    if report_dir.is_file() and report_dir.name == "report.json":
        report_json_path = report_dir
        report_dir = report_dir.parent
    else:
        report_json_path = report_dir / "report.json"

    if not report_json_path.exists():
        raise FileNotFoundError(f"report.json not found in {report_dir}")

    payload = json.loads(report_json_path.read_text(encoding="utf-8"))
    all_products = payload.get("products", [])

    # Filter out plain/printless garments
    printed_products = [
        p
        for p in all_products
        if not is_plain(p.get("title", ""))
        and p.get("theme") not in (NAO_ESTAMPADA, "nao-estampada", "lisa", "basica")
    ]

    # Group products by theme
    by_theme: dict[str, list[dict[str, Any]]] = {}
    for p in printed_products:
        t = (p.get("theme") or "Geral").strip()
        by_theme.setdefault(t, []).append(p)

    # Order themes by total market velocity and listing depth
    def _theme_sort_key(item: tuple[str, list[dict[str, Any]]]) -> tuple[float, int]:
        _, prods = item
        total_vel = sum(float(p.get("velocity_per_day") or 0.0) for p in prods)
        return (total_vel, len(prods))

    sorted_themes = sorted(by_theme.items(), key=_theme_sort_key, reverse=True)[:max_themes]

    # Temporary staging root for building pack before compression
    staging_dir = Path(tempfile.mkdtemp(prefix="art_pack_staging_"))
    catalog_rows: list[dict[str, Any]] = []

    try:
        theme_idx = 1
        for theme_name, prods in sorted_themes:
            # Sort products within theme: breakout priority, then daily velocity, then total sales
            def _prod_sort_key(p: dict[str, Any]) -> tuple[int, float, int]:
                is_bo = 1 if p.get("is_breakout") else 0
                vel = float(p.get("velocity_per_day") or 0.0)
                sold = int(p.get("sold_count") or 0)
                return (is_bo, vel, sold)

            ranked_products = sorted(prods, key=_prod_sort_key, reverse=True)
            chosen_products = ranked_products[:max_items_per_theme]
            if not chosen_products:
                continue

            niche_folder_name = f"{theme_idx:02d}_{_clean_niche_slug(theme_name)}"
            niche_dir = staging_dir / niche_folder_name
            niche_dir.mkdir(parents=True, exist_ok=True)

            is_single_item = len(chosen_products) == 1

            for p_idx, prod in enumerate(chosen_products):
                item_id = int(prod.get("item_id") or 0)
                spec = generate_print_spec(prod, theme_name)

                catalog_rows.append(
                    {
                        "item_id": spec["item_id"],
                        "theme": spec["theme"],
                        "title": spec["title"],
                        "price_brl": f"{spec['price_brl']:.2f}",
                        "velocity_per_day": f"{spec['velocity_per_day']:.1f}",
                        "technique": spec["technique"],
                        "print_size": spec["print_size"],
                        "shopee_url": spec["shopee_url"],
                    }
                )

                # Determine target directory for product assets
                if is_single_item:
                    item_dir = niche_dir
                else:
                    item_dir = niche_dir / str(item_id)
                item_dir.mkdir(parents=True, exist_ok=True)

                # 1. Obtain or fetch reference mockup image
                mockup_src = _resolve_or_fetch_product_image(prod, theme_name, staging_dir)
                mockup_dest = item_dir / "mockup_referencia.jpg"
                if mockup_src and mockup_src.exists():
                    # Why: Resave mockup image at quality 85 to normalize formats, apply JPEG
                    # optimization, and prevent large uncompressed photos from bloating the pack.
                    with Image.open(mockup_src) as m_img:
                        if m_img.mode != "RGB":
                            m_img = m_img.convert("RGB")
                        m_img.save(mockup_dest, format="JPEG", quality=85, optimize=True)
                else:
                    # Fallback blank image
                    fallback_img = Image.new("RGB", (800, 800), (240, 240, 240))
                    fallback_img.save(mockup_dest, format="JPEG", quality=85, optimize=True)

                # 2. Generate 1:1 high-density artwork crop
                crop_dest = item_dir / "grafismo_recorte.jpg"
                crop_print_artwork(mockup_dest, crop_dest)

                # 3. Write individual technical sheet
                ficha_dest = item_dir / "ficha_tecnica.txt"
                ficha_dest.write_text(_format_ficha_tecnica(spec), encoding="utf-8")

            theme_idx += 1

        # Write root CATALOGO_GERAL.csv
        csv_path = staging_dir / "CATALOGO_GERAL.csv"
        csv_headers = [
            "item_id",
            "theme",
            "title",
            "price_brl",
            "velocity_per_day",
            "technique",
            "print_size",
            "shopee_url",
        ]
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=csv_headers)
            writer.writeheader()
            for r in catalog_rows:
                writer.writerow(r)

        # Write root LEIA-ME_GUIA_DE_ESTAMPARIA.txt
        readme_path = staging_dir / "LEIA-ME_GUIA_DE_ESTAMPARIA.txt"
        readme_path.write_text(_generate_technician_guide(), encoding="utf-8")

        # Compress everything into pack_estampas_semana.zip
        target_zip = (
            Path(output_zip_path)
            if output_zip_path is not None
            else (report_dir / "pack_estampas_semana.zip")
        )
        target_zip.parent.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(target_zip, "w", zipfile.ZIP_DEFLATED) as zf:
            archive_files = []
            for root, _dirs, files in os.walk(staging_dir):
                for file in files:
                    if file.startswith("."):
                        continue
                    full_p = Path(root) / file
                    rel_p = full_p.relative_to(staging_dir)
                    # Exclude internal staging folders
                    if str(rel_p).startswith(("downloads", "placeholders")):
                        continue
                    archive_files.append((full_p, str(rel_p)))

            archive_files.sort(key=lambda x: x[1])
            for full_p, arc_name in archive_files:
                zf.write(full_p, arcname=arc_name)

        # Mirror distribution targets:
        # 1. data/reports/latest_pack.zip
        latest_pack_path = get_settings().data_dir / "reports" / "latest_pack.zip"
        latest_pack_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target_zip, latest_pack_path)

        # 2. web/public/downloads/pack_estampas_semana.zip
        if copy_to_web:
            web_downloads_dir = PROJECT_ROOT / "web" / "public" / "downloads"
            web_downloads_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target_zip, web_downloads_dir / "pack_estampas_semana.zip")

        logger.info(
            "Weekly art pack generated: %s (mirrored to latest_pack.zip%s)",
            target_zip,
            " & downloads" if copy_to_web else "",
        )
        return target_zip

    finally:
        shutil.rmtree(staging_dir, ignore_errors=True)


def main() -> int:
    """CLI entrypoint for building weekly art packs."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="Weekly Real Print Art Pack Generator")
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Path to report directory containing report.json (defaults to latest)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional output ZIP path",
    )
    args = parser.parse_args()

    report_dir = args.report
    if report_dir is None:
        reports_dir = get_settings().data_dir / "reports"
        if not reports_dir.exists():
            print("Error: data/reports directory does not exist")
            return 1
        valid_dirs = sorted(d for d in reports_dir.iterdir() if (d / "report.json").exists())
        if not valid_dirs:
            print("Error: No report directories with report.json found")
            return 1
        report_dir = valid_dirs[-1]

    pack_path = build_weekly_art_pack(report_dir, args.output)
    print(f"Art pack created: {pack_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
