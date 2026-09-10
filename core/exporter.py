"""Backend Sanitizer & Exporter for the Client-Facing Intelligence Portal.

Why: Transforms raw weekly Shopee scraper reports into a clean, safe, immutable
public dataset for the Next.js portal. Enforces a strict allowlist projection
guaranteeing zero leakage of private merchant identifiers, seller IDs, CNPJs,
or session tokens while compiling macro metrics, niche rankings, fabric radar,
and mutually exclusive production directives.
"""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps

from core.config import PROJECT_ROOT, get_settings

logger = logging.getLogger(__name__)

MONTHS_PT = {
    1: "Janeiro",
    2: "Fevereiro",
    3: "Março",
    4: "Abril",
    5: "Maio",
    6: "Junho",
    7: "Julho",
    8: "Agosto",
    9: "Setembro",
    10: "Outubro",
    11: "Novembro",
    12: "Dezembro",
}

FORBIDDEN_LEAK_KEYS = {
    "shop_id",
    "shop_name",
    "cnpj",
    "razao_social",
    "nome_fantasia",
    "notes",
    "cookies",
    "cookie",
    "token",
    "headers",
    "auth",
}

_CDN_HEADERS = {
    "Referer": "https://shopee.com.br/",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36"
    ),
}


def _theme_slug(theme: str) -> str:
    """Normalize a theme label into an ASCII hyphen-separated identifier."""
    normalized = unicodedata.normalize("NFKD", theme.strip().lower())
    ascii_only = "".join(c for c in normalized if not unicodedata.combining(c))
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_only).strip("-")
    return slug or "sem-tema"


def get_latest_report_dir() -> Path:
    """Locate the latest generated report directory within the data storage.

    Why: The exporter needs a predictable fallback when the caller does not
    explicitly specify an input report folder.
    """
    reports_dir = get_settings().data_dir / "reports"
    if not reports_dir.exists():
        raise FileNotFoundError(f"Reports directory does not exist: {reports_dir}")
    dirs = sorted((d for d in reports_dir.iterdir() if d.is_dir() and (d / "report.json").exists()))
    if not dirs:
        raise FileNotFoundError(
            f"No valid report directories with report.json found in {reports_dir}"
        )
    return dirs[-1]


def format_period_label(date_str: str) -> str:
    """Build a human-readable Brazilian Portuguese period label for the portal header.

    Why: Portal users expect localized week markers (e.g. 'Semana 36 • Setembro 2026')
    to quickly orient their production cycles.
    """
    dt: datetime | None = None
    if date_str:
        for fmt in ("%Y%m%dT%H%M%SZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(date_str, fmt)
                break
            except ValueError:
                continue
    if dt is None:
        dt = datetime.now()

    week_num = dt.isocalendar()[1]
    month_name = MONTHS_PT.get(dt.month, "Mês")
    return f"Semana {week_num} • {month_name} {dt.year}"


def create_svg_placeholder(output_path: Path, title: str) -> None:
    """Write a sleek minimalist SVG placeholder when product images are missing.

    Why: Avoids broken image links in the public portal interface while preserving
    clean visual aesthetics for high-velocity listings without reference photos.
    """
    disp_title = (title[:33] + "...") if len(title) > 36 else title
    safe_title = (
        disp_title.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )

    svg_content = (
        '<svg width="600" height="600" viewBox="0 0 600 600" fill="none" '
        'xmlns="http://www.w3.org/2000/svg">\n'
        '  <rect width="600" height="600" fill="#18181B"/>\n'
        '  <rect x="20" y="20" width="560" height="560" rx="16" stroke="#27272A" '
        'stroke-width="2" stroke-dasharray="8 8"/>\n'
        '  <circle cx="300" cy="250" r="48" fill="#27272A"/>\n'
        '  <path d="M284 266L296 250L306 260L316 244L328 266H284Z" fill="#71717A"/>\n'
        '  <circle cx="316" cy="236" r="6" fill="#A1A1AA"/>\n'
        '  <text x="300" y="340" fill="#F4F4F5" font-family="sans-serif" font-size="18" '
        'font-weight="600" text-anchor="middle">Trend Scout • Preview</text>\n'
        f'  <text x="300" y="370" fill="#A1A1AA" font-family="sans-serif" font-size="14" '
        f'text-anchor="middle">{safe_title}</text>\n'
        '</svg>'
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(svg_content, encoding="utf-8")


def process_product_image(
    item_id: int,
    theme: str | None,
    cdn_url: str | None,
    ref_dir: Path,
    output_images_dir: Path,
) -> str:
    """Optimize, resize to max 600x600, and convert listing photos to webp for portal delivery.

    Why: High-resolution scraped images slow down web portal performance and consume excessive
    bandwidth; resizing to 600x600 WebP yields snappy loading with minimal payload size.
    """
    output_images_dir.mkdir(parents=True, exist_ok=True)

    webp_path = output_images_dir / f"{item_id}.webp"
    jpg_path = output_images_dir / f"{item_id}.jpg"
    svg_path = output_images_dir / f"{item_id}.svg"

    # Search reference directories for source file
    source_file: Path | None = None
    slug = _theme_slug(theme or "sem-tema")
    candidates = [
        ref_dir / slug / f"{item_id}.jpg",
        ref_dir / slug / f"{item_id}.png",
        ref_dir / slug / f"{item_id}.webp",
        ref_dir / (theme or "sem-tema") / f"{item_id}.jpg",
        ref_dir / "sem-tema" / f"{item_id}.jpg",
    ]
    for c in candidates:
        if c.is_file():
            source_file = c
            break

    if not source_file and ref_dir.exists():
        # Recursive lookup as fallback
        matches = list(ref_dir.glob(f"**/{item_id}.*"))
        if matches:
            source_file = matches[0]

    # If still not found and cdn_url provided, try download
    if not source_file and cdn_url:
        try:
            import httpx

            resp = httpx.get(cdn_url, headers=_CDN_HEADERS, timeout=4.0)
            if resp.status_code == 200 and resp.content:
                temp_src = output_images_dir / f"_temp_{item_id}.bin"
                temp_src.write_bytes(resp.content)
                source_file = temp_src
        except Exception as exc:
            logger.debug("Failed downloading CDN image for %s: %s", item_id, exc)

    if source_file and source_file.is_file():
        try:
            with Image.open(source_file) as img:
                img = ImageOps.exif_transpose(img)
                img.thumbnail((600, 600), Image.Resampling.LANCZOS)

                # Try saving as WebP
                try:
                    if img.mode not in ("RGB", "RGBA"):
                        img = img.convert("RGB")
                    img.save(webp_path, format="WEBP", quality=85, method=4)
                    if source_file.name.startswith("_temp_"):
                        source_file.unlink(missing_ok=True)
                    return f"/images/prints/{item_id}.webp"
                except Exception as webp_err:
                    logger.debug(
                        "WebP conversion failed for %s, falling back to JPG: %s", item_id, webp_err
                    )
                    rgb_img = img.convert("RGB") if img.mode != "RGB" else img
                    rgb_img.save(jpg_path, format="JPEG", quality=85)
                    if source_file.name.startswith("_temp_"):
                        source_file.unlink(missing_ok=True)
                    return f"/images/prints/{item_id}.jpg"
        except Exception as exc:
            logger.warning("Could not process image for product %s: %s", item_id, exc)
            if source_file.name.startswith("_temp_"):
                source_file.unlink(missing_ok=True)

    # Fallback to SVG placeholder
    create_svg_placeholder(svg_path, str(item_id))
    return f"/images/prints/{item_id}.svg"


def _derive_product_audit(title: str, theme: str, price_brl: float) -> dict[str, str]:
    """Infer technical garment manufacturing specs from title patterns and price benchmarks.

    Why: B2B apparel brands require production intelligence (pattern cutting, fabric weight,
    print technique, and profit margin estimation) to evaluate sample manufacturing viability.
    """
    title_lower = title.lower()

    # Modelagem / Corte
    if re.search(r"\b(oversized?|streetwear|over|street)\b", title_lower):
        corte = "Oversized Streetwear (Caimento Amplo)"
    elif re.search(r"\b(baby\s*look|feminina|blusinha|t-shirt)\b", title_lower):
        corte = "Baby Look / T-Shirt Feminina Ajustada"
    elif re.search(r"\b(kit\s*\d*|combo|pe[cç]as?)\b", title_lower):
        corte = "Kit Promocional Multi-peças"
    elif re.search(r"\b(infantil|crian[cç]a|juvenil)\b", title_lower):
        corte = "Modelagem Infantil Confort"
    elif re.search(r"\b(regata|manga\s*longa)\b", title_lower):
        corte = "Modelagem Especial / Variação Estacional"
    else:
        corte = "Regular Fit Unissex (Gola Redonda)"

    # Malha Sugerida
    if re.search(r"\b(30\.1|pentead[oa]|100%\s*algod[aã]o|algod[aã]o\s*premium)\b", title_lower):
        malha = "100% Algodão 30.1 Penteado (Toque Macio)"
    elif re.search(r"\b(confort|26\.1|pesad[oa])\b", title_lower):
        malha = "Algodão 26.1 Heavyweight Confort"
    elif re.search(r"\b(dry[\s-]?fit|poli[eé]ster|esportiv[oa])\b", title_lower):
        malha = "Poliéster Dry-Fit Esportivo UV"
    elif re.search(r"\b(ribana|canelad[oa]|gola\s*alta)\b", title_lower):
        malha = "Algodão 30.1 com Ribana Canelada 2x1"
    else:
        malha = "100% Algodão Meia Malha Padrão"

    # Técnica de Estampa
    if re.search(r"\b(dtf|costas?|costa)\b", title_lower):
        tecnica = "DTF Têxtil Digital Posterior (Alta Resolução)"
    elif re.search(r"\b(silk|plastisol|serigrafia)\b", title_lower):
        tecnica = "Silk Screen Plastisol (Alta Tiragem)"
    elif re.search(r"\b(sublima|total|full\s*print)\b", title_lower):
        tecnica = "Sublimação Têxtil Total"
    elif re.search(r"\b(bordad[oa])\b", title_lower):
        tecnica = "Bordado Computadorizado em Relevo"
    elif re.search(r"\b(vintage|retr[oô]|acid|estonad[oa])\b", title_lower):
        tecnica = "Silk Screen Corrosão / Efeito Estonado"
    else:
        tecnica = "DTF Têxtil Digital Frontal (Toque Zero)"

    # Estimativa de Margem Bruta
    if price_brl >= 55.0:
        margem = "Margem Elevada (~52% a 62%)"
    elif price_brl >= 38.0:
        margem = "Margem Sadia (~40% a 50%)"
    elif price_brl >= 28.0:
        margem = "Margem Moderada (~30% a 38%)"
    else:
        margem = "Margem Comprimida (~18% a 25%)"

    return {
        "corte_modelagem": corte,
        "malha_sugerida": malha,
        "tecnica_estampa": tecnica,
        "estimativa_margem": margem,
    }


def calculate_unit_economics(price_cents: int, theme: str | None = None) -> dict[str, Any]:
    """Calculate granular unit economics, marketplace fees, and confection net margin.

    Why: Confeccionistas need transparent unit-level profitability analysis to avoid
    negative or compressed margins driven by Shopee's fixed fee and commission structure,
    and to understand the financial leverage of multi-pack bundles (Kit 2).

    Args:
        price_cents: Retail listing price in integer cents (BRL).
        theme: Optional product theme context.

    Returns:
        Dictionary containing fee breakdown, manufacturing costs, net margin, status,
        smart recommendation, and Kit 2 profit simulation.
    """
    price_brl = round(price_cents / 100.0, 2)
    shopee_commission_pct = 20.0
    shopee_commission_brl = round(price_brl * 0.20, 2)
    shopee_fixed_fee_brl = 4.00
    blank_shirt_cost_brl = 14.00
    print_cost_brl = 7.00
    packaging_tax_brl = round(price_brl * 0.05 + 1.20, 2)
    total_cost_fees_brl = round(
        shopee_commission_brl
        + shopee_fixed_fee_brl
        + blank_shirt_cost_brl
        + print_cost_brl
        + packaging_tax_brl,
        2,
    )
    net_profit_brl = round(price_brl - total_cost_fees_brl, 2)
    net_margin_pct = round((net_profit_brl / max(price_brl, 1.0)) * 100, 1)

    if net_profit_brl >= 7.00:
        status = "viable"
        recommendation = "Margem sadia para venda avulsa e em escala."
    elif net_profit_brl >= 3.00:
        status = "tight"
        recommendation = (
            "Venda unitária viável com controle rígido de insumos. Ideal ofertar kit complementar."
        )
    else:
        status = "risk_single_item"
        recommendation = (
            "Alerta: Venda unitária com margem comprimida. "
            "Venda em KITS de 2 ou 3 peças para diluir a taxa fixa de R$ 4,00 da Shopee!"
        )

    # Kit 2 simulation (price_brl * 1.85)
    kit_price_brl = round(price_brl * 1.85, 2)
    kit_commission_brl = round(kit_price_brl * 0.20, 2)
    kit_fixed_fee_brl = 4.00
    kit_blank_cost_brl = 28.00  # 14.00 * 2
    kit_print_cost_brl = 14.00  # 7.00 * 2
    kit_packaging_tax_brl = round(kit_price_brl * 0.05 + 1.20, 2)
    kit_total_costs = round(
        kit_commission_brl
        + kit_fixed_fee_brl
        + kit_blank_cost_brl
        + kit_print_cost_brl
        + kit_packaging_tax_brl,
        2,
    )
    kit_simulated_profit_brl = round(kit_price_brl - kit_total_costs, 2)

    return {
        "price_brl": price_brl,
        "shopee_commission_pct": shopee_commission_pct,
        "shopee_commission_brl": shopee_commission_brl,
        "shopee_fixed_fee_brl": shopee_fixed_fee_brl,
        "blank_shirt_cost_brl": blank_shirt_cost_brl,
        "print_cost_brl": print_cost_brl,
        "packaging_tax_brl": packaging_tax_brl,
        "total_cost_fees_brl": total_cost_fees_brl,
        "net_profit_brl": net_profit_brl,
        "net_margin_pct": net_margin_pct,
        "status": status,
        "recommendation": recommendation,
        "kit_simulated_profit_brl": kit_simulated_profit_brl,
    }


def compute_fabric_radar(all_products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Aggregate volume and share of dominant apparel construction patterns.

    Why: Informs print shops whether demand is leaning toward high-end oversized cuts,
    promotional bundle packs, or premium combed cotton.
    """
    total_prods = len(all_products) or 1
    patterns = [
        {
            "name": "Algodão 30.1 / Penteado",
            "regex": r"\b(30\.1|pentead[oa]|100%\s*algod[aã]o|algod[aã]o\s*premium)\b",
            "highlight": "Padrão ouro em malharia",
            "comment": (
                "Presente na maioria absoluta dos líderes de giro, "
                "garantindo percepção de qualidade."
            ),
        },
        {
            "name": "Modelagem Oversized / Streetwear",
            "regex": r"\b(oversized?|streetwear|over)\b",
            "highlight": "Corte de maior valor percebido",
            "comment": (
                "Permite ticket médio superior (R$ 39 a R$ 65) e alta tração no público jovem."
            ),
        },
        {
            "name": "Kits Promocionais (2 a 5 Peças)",
            "regex": r"\b(kit\s*\d*|combo|pe[cç]as?)\b",
            "highlight": "Alavanca de ticket médio",
            "comment": (
                "Amortiza o frete por pedido e maximiza a receita bruta por transação."
            ),
        },
        {
            "name": "Estampa Costas / DTF Digital",
            "regex": r"\b(costas?|silk|dtf|sublima[cç][aã]o|full\s*print|costa)\b",
            "highlight": "Composição visual predominante",
            "comment": (
                "Frente minimalista combinada com arte dorsal ampla tem a maior taxa de conversão."
            ),
        },
        {
            "name": "Gola Ribana / Canelada",
            "regex": (
                r"\b(ribana|gola\s*redonda|gola\s*careca|gola\s*grossa|gola\s*alta|canelad[oa])\b"
            ),
            "highlight": "Acabamento estruturado",
            "comment": (
                "Golas caneladas fechadas aumentam durabilidade pós-lavagem e minimizam devoluções."
            ),
        },
    ]

    radar_items = []
    for pat in patterns:
        matched = [
            p for p in all_products if re.search(pat["regex"], p.get("title", ""), re.IGNORECASE)
        ]
        cnt = len(matched)
        share = round((cnt / total_prods) * 100.0, 1)
        radar_items.append(
            {
                "name": pat["name"],
                "feature": pat["name"],
                "count": cnt,
                "share_pct": share,
                "percentage": share,
                "highlight": pat["highlight"],
                "comment": pat["comment"],
                "description": pat["comment"],
            }
        )
    return radar_items


def compute_directives(
    niches_data: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Determine prioritized production actions with strict mutual exclusion.

    Why: Apparel factories must never receive conflicting guidance recommending
    both printing and pausing the same theme in the same weekly cycle.
    """
    # 1. Identify pause candidates (price wars, margin compression, low median price)
    pause_candidates = [
        n
        for n in niches_data
        if (n["price_p50_brl"] < 30.0 and n["share_pct"] >= 5.0)
        or n["status_key"] == "high_comp"
        or n["price_p50_brl"] < 28.0
    ]
    pause_candidates.sort(key=lambda x: (x["price_p50_brl"], -x["daily_velocity"]))
    pause_ids = {n["theme_id"] for n in pause_candidates}

    # 2. Identify print candidates (healthy median price, high velocity, excluding pause themes)
    print_candidates = [
        n
        for n in niches_data
        if n["theme_id"] not in pause_ids
        and (n["price_p50_brl"] >= 30.0 or n["status_key"] == "high_demand_low_comp")
    ]
    print_candidates.sort(
        key=lambda x: x["daily_velocity"] * max(x["price_p50_brl"], 1.0), reverse=True
    )

    if not print_candidates:
        # Fallback: choose top price themes
        print_candidates = sorted(niches_data, key=lambda x: x["price_p50_brl"], reverse=True)

    to_print_raw = print_candidates[:3]
    selected_print_ids = {n["theme_id"] for n in to_print_raw}

    # 3. Finalize pause directives strictly excluding all selected print themes
    to_pause_raw = [n for n in pause_candidates if n["theme_id"] not in selected_print_ids]
    if len(to_pause_raw) < 3:
        remaining = [
            n
            for n in niches_data
            if n["theme_id"] not in selected_print_ids
            and n["theme_id"] not in {p["theme_id"] for p in to_pause_raw}
        ]
        remaining.sort(key=lambda x: x["price_p50_brl"])
        to_pause_raw.extend(remaining[: 3 - len(to_pause_raw)])

    to_pause_raw = to_pause_raw[:3]

    # Double check strict mutual exclusion guarantee
    assert not (selected_print_ids & {n["theme_id"] for n in to_pause_raw}), (
        "Directives violation: print and pause themes overlap!"
    )

    # Format recommendations with strategic business context
    to_print = []
    for t in to_print_raw:
        tid = t["theme_id"]
        if "streetwear" in tid:
            action = (
                "Lotes prioritários em corte Oversized e malha 30.1. "
                "Alta demanda acima de R$ 39,00."
            )
        elif "religioso" in tid or "cristao" in tid:
            action = (
                "Estampas minimalistas com lettering e versículos. "
                "Margens saudáveis e alta recompra."
            )
        elif "k-pop" in tid:
            action = (
                "Nicho de maior valor mediano (R$ 42+). Foque em emblemas elegantes e lançamentos."
            )
        elif "pets" in tid or "animais" in tid:
            action = "Excelente giro diário. Aposte em estampas retrô de raças e frases afetivas."
        elif "rock" in tid or "musica" in tid:
            action = (
                "Alta aceitação com acabamento estonado e visual vintage. "
                "Baixa resistência de preço."
            )
        else:
            vel_int = int(round(t["daily_velocity"]))
            action = f"Forte aceleração (+{vel_int} peças/dia) e dispersão de preço equilibrada."

        to_print.append(
            {
                "theme_id": t["theme_id"],
                "name": t["name"],
                "p50_brl": t["price_p50_brl"],
                "daily_velocity": t["daily_velocity"],
                "action": action,
            }
        )

    to_pause = []
    for t in to_pause_raw:
        tid = t["theme_id"]
        med_fmt = f"{t['price_p50_brl']:.2f}"
        if "anime" in tid:
            reason = (
                f"Guerra de preços predatória em matrizes comuns. Mediana travada em R$ {med_fmt}."
            )
            mitigation = (
                "Pausar tiragens abertas. Produzir apenas estampas exclusivas sob encomenda."
            )
        elif "geek" in tid:
            reason = "Saturação de modelos repetitivos em malha sintética comprimindo o preço."
            mitigation = (
                "Substituir artes genéricas por releituras autorais ou paródias sofisticadas."
            )
        elif "basica" in tid or "lisa" in tid:
            reason = "Commodity pura de centavos. Taxas de marketplace inviabilizam lucro líquido."
            mitigation = (
                "Descontinuar anúncios avulsos e converter estoque em kits com estampa localizada."
            )
        else:
            reason = (
                f"Preço mediano comprimido em R$ {med_fmt} com múltiplos concorrentes diretos."
            )
            mitigation = (
                "Suspender produção de estoque e repor exclusivamente sob demanda confirmada."
            )

        to_pause.append(
            {
                "theme_id": t["theme_id"],
                "name": t["name"],
                "p50_brl": t["price_p50_brl"],
                "reason": reason,
                "mitigation": mitigation,
            }
        )

    return {"to_print": to_print, "to_pause": to_pause}


def _validate_zero_leakage(obj: Any) -> None:
    """Recursively inspect a data structure to guarantee no forbidden keys exist.

    Why: Accidental leakage of internal seller IDs, merchant names, or cookies to
    the client-facing JSON payload violates the platform's confidentiality contract.
    """
    if isinstance(obj, dict):
        for k, v in obj.items():
            if str(k).lower() in FORBIDDEN_LEAK_KEYS:
                raise ValueError(f"Zero leakage violation: forbidden key '{k}' found in payload!")
            _validate_zero_leakage(v)
    elif isinstance(obj, list):
        for item in obj:
            _validate_zero_leakage(item)


def export_client_report(
    report_dir: Path | None = None,
    output_dir: Path | None = None,
) -> Path:
    """Sanitize internal intelligence report and export portal assets and JSON data.

    Why: Primary entrypoint for publishing refreshed market intelligence to the
    public Next.js web portal without exposing sensitive competitor or internal data.

    Args:
        report_dir: Directory containing internal report.json (defaults to latest in data/reports).
        output_dir: Web root directory for public assets (defaults to PROJECT_ROOT/web/public).

    Returns:
        Path to the generated `client_report.json` file.
    """
    if report_dir is None:
        report_dir = get_latest_report_dir()
    else:
        report_dir = Path(report_dir)

    report_json_path = report_dir / "report.json"
    if not report_json_path.is_file():
        raise FileNotFoundError(f"report.json not found in {report_dir}")

    if output_dir is None:
        public_dir = PROJECT_ROOT / "web" / "public"
    else:
        public_dir = Path(output_dir)

    data_dir = public_dir / "data"
    images_dir = public_dir / "images" / "prints"
    data_dir.mkdir(parents=True, exist_ok=True)
    images_dir.mkdir(parents=True, exist_ok=True)

    with open(report_json_path, "r", encoding="utf-8") as f:
        payload = json.loads(f.read())

    all_products: list[dict[str, Any]] = payload.get("products", [])
    raw_gen_at = payload.get("generated_at", "")
    report_id = (
        report_dir.name
        if report_dir.name
        else (raw_gen_at or datetime.now().strftime("%Y%m%dT%H%M%SZ"))
    )
    period_label = format_period_label(raw_gen_at)

    # --- Market Overview Metrics ---
    monitored_products_count = payload.get("product_count") or len(all_products)
    printed_products_count = payload.get("printed_count") or monitored_products_count

    total_daily_vel = sum(float(p.get("velocity_per_day") or 0.0) for p in all_products)
    if total_daily_vel == 0.0:
        total_daily_vel = sum(float(p.get("sold_count") or 0.0) for p in all_products)
    daily_volume_velocity = round(total_daily_vel, 1)
    weekly_estimated_volume = int(round(daily_volume_velocity * 7))

    total_revenue_weekly = sum(
        (float(p.get("velocity_per_day") or 0.0) * 7) * (float(p.get("price_cents", 0)) / 100.0)
        for p in all_products
    )
    if total_revenue_weekly == 0.0:
        total_revenue_weekly = sum(
            float(p.get("sold_count") or 0.0) * (float(p.get("price_cents", 0)) / 100.0)
            for p in all_products
        )
    weekly_estimated_revenue_brl = round(total_revenue_weekly, 2)

    all_prices = sorted(p.get("price_cents", 0) for p in all_products if p.get("price_cents"))
    p25_c = payload.get("price_p25_cents")
    p50_c = payload.get("price_p50_cents")
    p75_c = payload.get("price_p75_cents")
    if (not p50_c) and all_prices:
        p25_c = all_prices[len(all_prices) // 4]
        p50_c = all_prices[len(all_prices) // 2]
        p75_c = all_prices[(len(all_prices) * 3) // 4]
    p25_brl = round((p25_c or 0) / 100.0, 2)
    p50_brl = round((p50_c or 0) / 100.0, 2)
    p75_brl = round((p75_c or 0) / 100.0, 2)

    # --- Top 10 Niches ---
    opps = payload.get("theme_opportunities") or {}
    vel_map = dict(payload.get("theme_velocities", []))
    count_map = dict(payload.get("theme_counts", []))

    excluded_slugs = {"nao-estampada", "lisa", "basica", "sem-tema"}
    candidate_themes = [
        t
        for t in dict.fromkeys(list(count_map.keys()) + list(vel_map.keys()))
        if t and _theme_slug(t) not in excluded_slugs
    ]

    def _theme_sort_key(t_name: str) -> tuple[float, int]:
        v = vel_map.get(t_name)
        if v is None:
            prods = [p for p in all_products if p.get("theme") == t_name]
            v = sum(float(p.get("velocity_per_day") or 0.0) for p in prods)
        c = count_map.get(t_name, 0)
        return (float(v), int(c))

    candidate_themes.sort(key=_theme_sort_key, reverse=True)
    top_themes = candidate_themes[:10]

    niches_data = []
    total_printed_ref = printed_products_count or 1
    for rank, theme_name in enumerate(top_themes, start=1):
        prods = [p for p in all_products if p.get("theme") == theme_name]
        t_prices = sorted(p.get("price_cents", 0) for p in prods if p.get("price_cents"))
        cnt = count_map.get(theme_name, len(prods))

        v = vel_map.get(theme_name)
        if v is None:
            v = sum(float(p.get("velocity_per_day") or 0.0) for p in prods)
            if v == 0.0:
                v = sum(float(p.get("sold_count") or 0.0) for p in prods)

        if t_prices:
            tp25 = round(t_prices[len(t_prices) // 4] / 100.0, 2)
            tp50 = round(t_prices[len(t_prices) // 2] / 100.0, 2)
            tp75 = round(t_prices[(len(t_prices) * 3) // 4] / 100.0, 2)
        else:
            tp25 = tp50 = tp75 = 0.0

        slug = _theme_slug(theme_name)
        opp = opps.get(theme_name) or opps.get(slug, {})
        status_label = opp.get("label") or (
            "Alta Procura • Pouca Concorrência" if tp50 >= 30.0 else "Mercado Estável"
        )
        badge_color = opp.get("badge_color") or ("emerald" if tp50 >= 30.0 else "slate")
        status_key = opp.get("status_key") or ("high_demand_low_comp" if tp50 >= 30.0 else "steady")

        share_pct = round((cnt / total_printed_ref) * 100.0, 1)

        niches_data.append(
            {
                "theme_id": slug,
                "name": theme_name.title(),
                "rank": rank,
                "share_pct": share_pct,
                "daily_velocity": round(float(v), 1),
                "price_p25_brl": tp25,
                "price_p50_brl": tp50,
                "price_p75_brl": tp75,
                "status_key": status_key,
                "status_label": status_label,
                "badge_color": badge_color,
            }
        )

    # --- Breakout Prints (12 to 16 items) ---
    raw_breakouts = payload.get("breakout_products", [])
    if not raw_breakouts:
        # Fallback: choose top accelerating products from products list
        def _vel_key(p: dict) -> tuple[float, float]:
            return (float(p.get("velocity_per_day") or 0.0), float(p.get("sold_count") or 0.0))

        raw_breakouts = sorted(
            [
                p
                for p in all_products
                if _theme_slug(p.get("theme") or "") not in ("nao-estampada", "lisa")
            ],
            key=_vel_key,
            reverse=True,
        )

    target_breakouts = raw_breakouts[:16]
    if len(target_breakouts) < 12 and len(all_products) >= 12:
        # Pad with remaining top products if needed
        seen_ids = {p.get("item_id") for p in target_breakouts}
        for p in all_products:
            if p.get("item_id") not in seen_ids:
                target_breakouts.append(p)
                seen_ids.add(p.get("item_id"))
                if len(target_breakouts) >= 12:
                    break

    ref_dir = get_settings().data_dir / "reference"
    breakout_prints = []
    for item in target_breakouts:
        item_id = int(item["item_id"])
        theme_name = item.get("theme") or "Geral / Moda"
        price_cents = item.get("price_cents") or 0
        price_brl = round(price_cents / 100.0, 2)
        sold_count = int(item.get("sold_count") or 0)
        daily_vel = round(float(item.get("velocity_per_day") or 0.0), 1)

        if daily_vel > 0:
            vel_label = f"+{int(round(daily_vel)):,} peças/dia".replace(",", ".")
        elif sold_count > 0:
            vel_label = f"+{sold_count:,} un. vendidas".replace(",", ".")
        else:
            vel_label = "Em aceleração"

        img_rel_url = process_product_image(
            item_id=item_id,
            theme=item.get("theme"),
            cdn_url=item.get("image_url"),
            ref_dir=ref_dir,
            output_images_dir=images_dir,
        )

        audit_data = _derive_product_audit(
            title=item.get("title", ""),
            theme=theme_name,
            price_brl=price_brl,
        )
        unit_econ = calculate_unit_economics(
            price_cents=price_cents,
            theme=theme_name,
        )

        raw_link = item.get("url") or f"https://shopee.com.br/product/{item.get('shop_id')}/{item_id}"
        shopee_link = raw_link if raw_link.startswith("http") else f"https://shopee.com.br{raw_link}"

        breakout_prints.append(
            {
                "id": item_id,
                "title": item.get("title", "").strip(),
                "theme_name": theme_name.title(),
                "price_brl": price_brl,
                "sold_count": sold_count,
                "daily_velocity": daily_vel,
                "velocity_label": vel_label,
                "image_url": img_rel_url,
                "shopee_url": shopee_link,
                "shopeeUrl": shopee_link,
                "audit": audit_data,
                "unit_economics": unit_econ,
                "unitEconomics": unit_econ,
            }
        )

    # Attach unit economics to payload["breakouts"] if present in internal structure
    if "breakouts" in payload and isinstance(payload["breakouts"], list):
        for b in payload["breakouts"]:
            if isinstance(b, dict):
                b["unitEconomics"] = calculate_unit_economics(
                    b.get("price_cents", 0), b.get("theme")
                )
                b["unit_economics"] = b["unitEconomics"]

    # --- Fabric Radar ---
    fabric_radar = compute_fabric_radar(all_products)

    # --- Directives (Strict Mutual Exclusion) ---
    directives = compute_directives(niches_data)

    # Construct the strictly allowlisted public dictionary
    public_payload = {
        "meta": {
            "report_id": report_id,
            "generated_at": raw_gen_at or datetime.now().strftime("%Y%m%dT%H%M%SZ"),
            "period_label": period_label,
            "marketplace": "Shopee Brasil",
        },
        "market_overview": {
            "monitored_products_count": monitored_products_count,
            "printed_products_count": printed_products_count,
            "daily_volume_velocity": daily_volume_velocity,
            "weekly_estimated_volume": weekly_estimated_volume,
            "weekly_estimated_revenue_brl": weekly_estimated_revenue_brl,
            "price_benchmark": {
                "p25": p25_brl,
                "p50": p50_brl,
                "p75": p75_brl,
            },
        },
        "niches": niches_data,
        "breakout_prints": breakout_prints,
        "fabric_radar": fabric_radar,
        "directives": directives,
    }

    # Zero leakage validation
    _validate_zero_leakage(public_payload)

    out_file = data_dir / "client_report.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(public_payload, f, indent=2, ensure_ascii=False)

    logger.info("Successfully exported client report to %s", out_file)
    return out_file
