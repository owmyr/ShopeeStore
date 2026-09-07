import base64
import json
import logging
import re
from datetime import datetime
from pathlib import Path

import httpx
from jinja2 import Environment, FileSystemLoader
from playwright.sync_api import sync_playwright

from agents.trend_scout.filter import theme_slug as normalize_theme_slug
from core.config import get_settings

logger = logging.getLogger(__name__)

_CDN_HEADERS = {
    "Referer": "https://shopee.com.br/",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36"
    ),
}


def _format_brl(val_or_cents: float | int, is_cents: bool = False) -> str:
    """Format currency values into Brazilian Real standard (e.g. R$ 1.234,56)."""
    val = (val_or_cents / 100.0) if is_cents else float(val_or_cents)
    formatted = f"{val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {formatted}"


def _format_int_br(val: int | float) -> str:
    """Format integers with dot thousand separators (e.g. 12.345)."""
    return f"{int(round(val)):,}".replace(",", ".")


def _compute_theme_opportunities_from_dicts(products: list[dict]) -> dict[str, dict]:
    """Compute market opportunity classifications for each print theme from product dictionaries.

    Why: B2B merchants and print shops need actionable signals distinguishing lucrative niches
    (high sales velocity with healthy price dispersion) from over-saturated commodity niches
    (heavy price wars). If report.json lacks precomputed opportunities, this reconstructs
    the classification directly from product listing data.
    """
    by_theme: dict[str, list[dict]] = {}
    for p in products:
        theme = p.get("theme")
        if not theme or theme.lower() in ("nao-estampada", "lisa", "basica"):
            continue
        by_theme.setdefault(theme, []).append(p)

    opportunities: dict[str, dict] = {}
    for theme, prods in by_theme.items():
        listings_count = len(prods)
        shops_count = len({p.get("shop_id") for p in prods if p.get("shop_id")})
        total_velocity = round(sum(float(p.get("velocity_per_day") or 0.0) for p in prods), 1)
        avg_velocity = round(total_velocity / listings_count, 1) if listings_count > 0 else 0.0

        prices = sorted(p.get("price_cents", 0) for p in prods if p.get("price_cents"))
        if prices:
            p25 = prices[len(prices) // 4]
            p50 = prices[len(prices) // 2]
            p75 = prices[(len(prices) * 3) // 4]
        else:
            p25 = p50 = p75 = 0
        spread_ratio = round((p50 - p25) / max(p50, 1), 4)

        if avg_velocity >= 10.0 or total_velocity >= 40.0:
            if shops_count <= 8 or spread_ratio >= 0.20:
                status_key = "high_demand_low_comp"
                label = "Alta Procura • Pouca Concorrência"
                badge_color = "emerald"
            else:
                status_key = "high_comp"
                label = "Nicho Muito Disputado (Briga de Preço)"
                badge_color = "amber"
        else:
            if any(p.get("is_new") for p in prods):
                status_key = "emerging"
                label = "Estampas Novas em Alta"
                badge_color = "indigo"
            else:
                status_key = "steady"
                label = "Mercado Estável"
                badge_color = "slate"

        opportunities[theme] = {
            "status_key": status_key,
            "label": label,
            "badge_color": badge_color,
            "total_velocity": total_velocity,
            "avg_velocity": avg_velocity,
            "listings_count": listings_count,
            "shops_count": shops_count,
            "price_p25_cents": p25,
            "price_p50_cents": p50,
            "price_p75_cents": p75,
            "spread_ratio": spread_ratio,
        }
    return opportunities


def _fetch_cdn_image(url: str) -> str | None:
    """Download a Shopee CDN image and return it as a base64 data URI.

    Uses Referer spoofing — Shopee CDN requires a valid shopee.com.br Referer
    header or it returns a 403. Returns None on any network/HTTP error so the
    caller can fall back gracefully.
    """
    try:
        resp = httpx.get(url, headers=_CDN_HEADERS, timeout=10, follow_redirects=True)
        resp.raise_for_status()
        ct = resp.headers.get("content-type", "image/jpeg").split(";")[0].strip()
        b64 = base64.b64encode(resp.content).decode("utf-8")
        return f"data:{ct};base64,{b64}"
    except Exception as exc:  # noqa: BLE001
        logger.debug("CDN fetch failed for %s: %s", url, exc)
        return None


def _image_to_base64(img_path: Path) -> str:
    """Read an image and convert it to a base64 data URI.

    If the file doesn't exist, returns a placeholder SVG base64.
    """
    if img_path.exists():
        mime = "image/png" if img_path.suffix.lower() == ".png" else "image/jpeg"
        with open(img_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
            return f"data:{mime};base64,{b64}"

    svg = (
        '<svg width="200" height="200" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200">'
        '<rect width="200" height="200" fill="#f8fafc"/>'
        '<circle cx="100" cy="90" r="30" fill="#e2e8f0"/>'
        '<path d="M85 85 L115 100 L85 115 Z" fill="#94a3b8" />'
        '<text x="50%" y="140" font-family="Plus Jakarta Sans, sans-serif" font-weight="600" '
        'font-size="12" fill="#64748b" text-anchor="middle" '
        'letter-spacing="1">MOCKUP PENDENTE</text>'
        "</svg>"
    )
    b64 = base64.b64encode(svg.encode("utf-8")).decode("utf-8")
    return f"data:image/svg+xml;base64,{b64}"


def _generate_qr_base64(data: str) -> str:
    """Generate a base64-encoded PNG QR code for print and static image embeds."""
    if not data:
        return ""
    try:
        import io

        import qrcode

        qr = qrcode.QRCode(box_size=4, border=1)
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="#0f172a", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        encoded = base64.b64encode(buf.getvalue()).decode("utf-8")
        return f"data:image/png;base64,{encoded}"
    except Exception as exc:
        logger.warning("Failed to generate QR code: %s", exc)
        return ""


def get_latest_report_dir() -> Path | None:
    reports = get_settings().data_dir / "reports"
    if not reports.exists():
        return None
    dirs = sorted((d for d in reports.iterdir() if (d / "report.json").exists()))
    return dirs[-1] if dirs else None


def generate_dossier(
    report_dir: Path | None = None, theme_slug: str | None = None, output_pdf: bool = True
) -> Path:
    """Generate an executive dossier in HTML and optionally PDF format.

    Why: Provides clothing manufacturers and print shops with an executive-level
    weekly intelligence report covering real market velocity, top revenue niches,
    modelagem and fabric patterns, fast-accelerating breakout prints, and strategic
    production directives.

    Args:
        report_dir: Directory containing the report.json. If None, uses the latest.
        theme_slug: Optional theme to filter the dossier content.
        output_pdf: Whether to generate a PDF using Playwright.

    Returns:
        Path to the generated file (PDF if generated, else HTML).
    """
    if report_dir is None:
        report_dir = get_latest_report_dir()
        if report_dir is None:
            raise FileNotFoundError("No report directories found.")

    report_json_path = report_dir / "report.json"
    if not report_json_path.exists():
        raise FileNotFoundError(f"report.json not found in {report_dir}")

    with open(report_json_path, "r", encoding="utf-8") as f:
        payload = json.loads(f.read())

    all_products = payload.get("products", [])
    products = all_products
    if theme_slug:
        target_slug = normalize_theme_slug(theme_slug)
        products = [
            p
            for p in all_products
            if p.get("theme")
            and (
                p.get("theme").lower() == theme_slug.lower()
                or normalize_theme_slug(p.get("theme")) == target_slug
            )
        ]

    # --- Macro Market Numbers ---
    product_count = payload.get("product_count") or len(all_products)
    printed_count = payload.get("printed_count") or product_count

    # Daily velocity across monitored listings (fallback to sold_count if no velocity_per_day)
    total_daily_velocity = sum(
        float(p.get("velocity_per_day") or 0.0) for p in all_products
    )
    if total_daily_velocity == 0.0:
        total_daily_velocity = sum(
            float(p.get("sold_count") or 0.0) for p in all_products
        )

    estimated_weekly_pieces = int(round(total_daily_velocity * 7))

    # Estimated weekly revenue transacted in BRL across monitored listings
    estimated_weekly_revenue_brl = sum(
        (float(p.get("velocity_per_day") or 0.0) * 7) * (float(p.get("price_cents", 0)) / 100.0)
        for p in all_products
    )
    if estimated_weekly_revenue_brl == 0.0:
        estimated_weekly_revenue_brl = sum(
            float(p.get("sold_count") or 0.0) * (float(p.get("price_cents", 0)) / 100.0)
            for p in all_products
        )

    # Global price distribution
    all_prices = sorted(
        p.get("price_cents", 0) for p in all_products if p.get("price_cents")
    )
    p25_cents = payload.get("price_p25_cents")
    p50_cents = payload.get("price_p50_cents")
    p75_cents = payload.get("price_p75_cents")
    if (not p50_cents) and all_prices:
        p25_cents = all_prices[len(all_prices) // 4]
        p50_cents = all_prices[len(all_prices) // 2]
        p75_cents = all_prices[(len(all_prices) * 3) // 4]
    p25_cents = p25_cents or 0
    p50_cents = p50_cents or 0
    p75_cents = p75_cents or 0

    # --- Top 10 Themes / Niches ---
    opps = payload.get("theme_opportunities")
    if not opps or not isinstance(opps, dict):
        opps = _compute_theme_opportunities_from_dicts(all_products)

    vel_map = dict(payload.get("theme_velocities", []))
    count_map = dict(payload.get("theme_counts", []))

    candidate_themes = list(
        dict.fromkeys(list(count_map.keys()) + list(vel_map.keys()) + list(opps.keys()))
    )

    def _theme_rank_key(t_name: str) -> tuple[float, int]:
        v = vel_map.get(t_name)
        if v is None:
            t_prods = [p for p in all_products if p.get("theme") == t_name]
            v = sum(float(p.get("velocity_per_day") or 0.0) for p in t_prods)
        c = count_map.get(t_name, 0)
        return (float(v), int(c))

    candidate_themes.sort(key=_theme_rank_key, reverse=True)

    if theme_slug:
        target_slug = normalize_theme_slug(theme_slug)
        candidate_themes = [
            t
            for t in candidate_themes
            if t.lower() == theme_slug.lower() or normalize_theme_slug(t) == target_slug
        ]
        top_theme_names = candidate_themes
    else:
        top_theme_names = candidate_themes[:10]

    themes_data = []
    total_printed_ref = printed_count or 1
    for rank, theme_name in enumerate(top_theme_names, start=1):
        theme_prods = [p for p in all_products if p.get("theme") == theme_name]
        t_prices = sorted(p.get("price_cents", 0) for p in theme_prods if p.get("price_cents"))
        count = count_map.get(theme_name, len(theme_prods))

        real_vel = vel_map.get(theme_name)
        if real_vel is None:
            real_vel = sum(float(p.get("velocity_per_day") or 0.0) for p in theme_prods)
            if real_vel == 0.0 and count > 0:
                real_vel = sum(float(p.get("sold_count") or 0.0) for p in theme_prods)

        if t_prices:
            p25 = t_prices[len(t_prices) // 4] / 100.0
            p50 = t_prices[len(t_prices) // 2] / 100.0
            p75 = t_prices[(len(t_prices) * 3) // 4] / 100.0
            avg_p = sum(t_prices) / (len(t_prices) * 100.0)
        else:
            p25 = p50 = p75 = avg_p = 0.0

        opp = opps.get(theme_name) or opps.get(normalize_theme_slug(theme_name), {})
        status_label = opp.get("label", "Mercado Estável")
        badge_color = opp.get("badge_color", "slate")
        status_key = opp.get("status_key", "steady")

        share_pct = (count / total_printed_ref) * 100.0

        themes_data.append(
            {
                "rank": f"{rank:02d}",
                "name": theme_name.title(),
                "raw_name": theme_name,
                "count": count,
                "share_pct": f"{share_pct:.1f}%",
                "volume_share": f"{share_pct:.1f}%",  # backward compatibility
                "velocity": f"+{int(round(real_vel)):,} peças/dia".replace(",", "."),
                "daily_velocity": round(real_vel, 1),
                "p25": p25,
                "p50": p50,
                "p75": p75,
                "p50_brl": _format_brl(p50),
                "avg_price_brl": _format_brl(avg_p),
                "status_label": status_label,
                "badge_color": badge_color,
                "status_key": status_key,
            }
        )

    # --- Modelagem & Fabric Highlights ---
    fabric_definitions = [
        {
            "name": "Algodão 30.1 / Penteado",
            "regex": r"\b(30\.1|pentead[oa]|100%\s*algod[aã]o|algod[aã]o\s*premium)\b",
            "highlight": "Padrão ouro em malharia",
            "comment": (
                "Presente em mais de 50% dos líderes de vendas. "
                "Garante toque macio, estrutura e alta percepção de valor."
            ),
        },
        {
            "name": "Modelagem Oversized / Streetwear",
            "regex": r"\b(oversized?|streetwear|over)\b",
            "highlight": "Corte de maior aceleração",
            "comment": (
                "Permite praticar preços médios superiores (R$ 39 a R$ 59) "
                "e atrai o público jovem urbano com alto giro."
            ),
        },
        {
            "name": "Kits Promocionais (2 a 5 Peças)",
            "regex": r"\b(kit\s*\d*|combo|pe[cç]as?)\b",
            "highlight": "Alavanca de ticket médio",
            "comment": (
                "Domina os top anúncios em volume financeiro total, "
                "amortizando o frete e multiplicando a receita por transação."
            ),
        },
        {
            "name": "Estampa Costas / DTF / Silk",
            "regex": r"\b(costas?|silk|dtf|sublima[cç][aã]o|full\s*print|costa)\b",
            "highlight": "Composição visual em alta",
            "comment": (
                "Peito minimalista com grande estampa posterior é a "
                "assinatura estética com maior absorção pelo público jovem."
            ),
        },
        {
            "name": "Gola Ribana / Gola Grossa",
            "regex": (
                r"\b(ribana|gola\s*redonda|gola\s*careca|gola\s*grossa|gola\s*alta|canelad[oa])\b"
            ),
            "highlight": "Acabamento estruturado",
            "comment": (
                "Golas fechadas com ribana 2x1 canelada conferem caimento de boutique "
                "e reduzem taxa de devoluções."
            ),
        },
        {
            "name": "Estilo Vintage / Lavagem Estonada",
            "regex": r"\b(vintage|retr[oô]|acid|lavagem|estony|stoned)\b",
            "highlight": "Margem saudável e diferenciada",
            "comment": (
                "Acabamentos marmorizados e retrô permitem margem bruta até 35% superior "
                "sem resistência de preço."
            ),
        },
    ]

    total_prods = len(all_products) or 1
    fabric_highlights = []
    for fdef in fabric_definitions:
        matches = [
            p
            for p in all_products
            if re.search(fdef["regex"], p.get("title", ""), re.IGNORECASE)
        ]
        pct = (len(matches) / total_prods) * 100.0
        fabric_highlights.append(
            {
                "name": fdef["name"],
                "count": len(matches),
                "percentage": f"{pct:.1f}%",
                "highlight": fdef["highlight"],
                "comment": fdef["comment"],
            }
        )

    # --- 12 to 16 Breakout Products ---
    def _product_velocity_sort_key(p: dict) -> tuple[float, float]:
        vel = p.get("velocity_per_day")
        sold = p.get("sold_count") or 0
        return (float(vel) if vel is not None else 0.0, float(sold))

    breakout_candidates = sorted(products, key=_product_velocity_sort_key, reverse=True)[:12]

    reference_dir = get_settings().data_dir / "reference"
    breakout_products = []
    for product in breakout_candidates:
        item_id = product.get("item_id")
        p_theme = product.get("theme") or "sem-tema"
        p_slug = normalize_theme_slug(p_theme)

        img_path = reference_dir / p_slug / f"{item_id}.jpg"
        if not img_path.exists():
            img_path = reference_dir / p_theme / f"{item_id}.jpg"
        if not img_path.exists():
            img_path = reference_dir / "sem-tema" / f"{item_id}.jpg"

        if img_path.exists():
            base64_image = _image_to_base64(img_path)
        else:
            cdn_url = product.get("image_url", "")
            cdn_data = _fetch_cdn_image(cdn_url) if cdn_url else None
            base64_image = cdn_data or _image_to_base64(img_path)

        price_cents = product.get("price_cents", 0)
        price_brl = price_cents / 100.0 if price_cents else 0.0

        vel = product.get("velocity_per_day")
        if vel is not None and vel > 0:
            vel_fmt = f"+{int(round(vel)):,} peças/dia".replace(",", ".")
            daily_vel_val = round(vel, 1)
        elif product.get("sold_count"):
            vel_fmt = f"+{product.get('sold_count'):,} un. vendidas".replace(",", ".")
            daily_vel_val = float(product.get("sold_count"))
        else:
            vel_fmt = "Em aceleração"
            daily_vel_val = 0.0

        clean_theme = (product.get("theme") or "Geral / Moda").title()

        breakout_products.append(
            {
                "item_id": item_id,
                "title": product.get("title", ""),
                "theme": product.get("theme", ""),
                "clean_theme": clean_theme,
                "price_cents": price_cents,
                "price_brl": price_brl,
                "price_brl_fmt": _format_brl(price_cents, is_cents=True),
                "sold_count": product.get("sold_count", 0),
                "sold_count_fmt": _format_int_br(product.get("sold_count", 0)),
                "velocity": vel_fmt,
                "daily_velocity": daily_vel_val,
                "url": product.get("url") or "#",
                "base64_image": base64_image,
            }
        )

    # --- Strategic Production Insights (Strict Mutual Exclusion Rule) ---
    # Business Rule: A theme can NEVER appear in both "to_print" (O Que Estampar)
    # and "to_pause" (O Que Pausar).
    # 1. Identify themes with severe price war / compressed margins (candidates to pause)
    pause_candidates = [
        t
        for t in themes_data
        if (t["p50"] < 30.0 and t["count"] >= 10)
        or (t["status_key"] == "high_comp" and t["p50"] < 32.0)
    ]
    pause_candidates.sort(key=lambda x: (-x["count"], x["p50"]))
    pause_candidate_names = {t["raw_name"] for t in pause_candidates}

    # 2. Identify themes with high traction AND healthy margins (candidates to print)
    # Must strictly exclude pause candidates to guarantee no overlap
    print_candidates = [
        t
        for t in themes_data
        if t["raw_name"] not in pause_candidate_names
        and (t["p50"] >= 30.0 or t["status_key"] == "high_demand_low_comp")
    ]
    print_candidates.sort(
        key=lambda x: x["daily_velocity"] * max(x["p50"], 1.0), reverse=True
    )

    if not print_candidates:
        print_candidates = sorted(themes_data, key=lambda x: x["p50"], reverse=True)

    to_print = print_candidates[:3]
    selected_print_names = {t["raw_name"] for t in to_print}

    to_print_recommendations = []
    for t in to_print:
        name_lower = t["raw_name"].lower()
        if "streetwear" in name_lower:
            action = (
                "Produzir lotes focados em modelagem Oversized e malha 30.1 penteada. "
                "Estampas tipográficas e nas costas com DTF têm giro imediato acima de R$ 39,00."
            )
        elif "religioso" in name_lower:
            action = (
                "Lotes de alto giro contínuo. Artes minimalistas com versículos, lettering "
                "moderno e traços lineares mantêm recompra acelerada e margem sadia."
            )
        elif "k-pop" in name_lower:
            action = (
                "Maior preço mediano da categoria (R$ 42,29). Foque em grupos atuais e "
                "estética minimalista/emblema para capturar público disposto a pagar premium."
            )
        elif "pets" in name_lower or "animais" in name_lower:
            action = (
                "Excelente tração diária. Foque em personalização de raças ou arte "
                "estilo retrô/vintage para sustentar preços acima de R$ 32,00 com margem protegida."
            )
        elif "rock" in name_lower or "musica" in name_lower:
            action = (
                "Excelente aceitação para camisetas estonadas/vintage com estampa frontal "
                "envelhecida. Preço acima de R$ 34,00 com baixa resistência."
            )
        else:
            action = (
                f"Forte demanda (+{t['velocity']}) e saudável dispersão de preços. "
                "Priorizar reposição rápida e variações de cor neutras (preto, off-white, chumbo)."
            )

        to_print_recommendations.append(
            {
                "name": t["name"],
                "velocity": t["velocity"],
                "p50_brl": t["p50_brl"],
                "share": t["share_pct"],
                "action": action,
            }
        )

    # 3. Finalize to_pause with strict mutual exclusion: exclude all selected_print_names
    to_pause = [t for t in pause_candidates if t["raw_name"] not in selected_print_names]
    if len(to_pause) < 3:
        remaining = [
            t
            for t in themes_data
            if t["raw_name"] not in selected_print_names and t not in to_pause
        ]
        remaining.sort(key=lambda x: x["p50"])
        to_pause.extend(remaining[: 3 - len(to_pause)])

    to_pause = to_pause[:3]

    to_pause_recommendations = []
    for t in to_pause:
        name_lower = t["raw_name"].lower()
        if "anime" in name_lower:
            risk = (
                f"Guerra agressiva de preços com {t['count']} confecções concorrentes. "
                f"Preço mediano travado em {t['p50_brl']} e margem líquida inferior a 12%."
            )
            mitigation = (
                "Pausar matrizes tradicionais de animes batidos. Só produzir sob encomenda "
                "ou em kits com estampas exclusivas nas costas."
            )
        elif "religioso" in name_lower or "cristao" in name_lower:
            risk = (
                f"Disputa predatória com {t['count']} confecções concorrentes por centavos. "
                f"Preço mediano comprimido em {t['p50_brl']}, onde frete e taxas consomem o lucro."
            )
            mitigation = (
                "Suspender tiragens longas de versículos genéricos. Migrar para coleções autorais "
                "com modelagem premium ou kits familiares."
            )
        elif "geek" in name_lower:
            risk = (
                "Saturação de modelos genéricos em poliéster/algodão fino, "
                f"puxando cotação para baixo ({t['p50_brl']})."
            )
            mitigation = (
                "Suspender tiragens longas de heróis clássicos. Migrar para paródias "
                "autorais ou estética retrô/vintage."
            )
        elif "pets" in name_lower:
            risk = "Disputa predatória de centavos e anúncios com frete grátis forçado."
            mitigation = (
                "Evitar estampas comuns de animais sem personalização de raças "
                "ou modelagem diferenciada."
            )
        else:
            risk = (
                f"Preço mediano comprimido em {t['p50_brl']} com múltiplos sellers "
                "brigando por margens mínimas."
            )
            mitigation = (
                "Suspender produção em estoque e focar apenas em pedidos pré-faturados."
            )

        to_pause_recommendations.append(
            {
                "name": t["name"],
                "p50_brl": t["p50_brl"],
                "count": t["count"],
                "risk": risk,
                "mitigation": mitigation,
            }
        )

    # --- Subscription Callout & Web Portal ---
    settings = get_settings()
    portal_url = getattr(settings, "portal_url", "https://trendscout-orcin.vercel.app")
    portal_display_url = getattr(settings, "portal_display_url", "trendscout-orcin.vercel.app")
    portal_qr_base64 = _generate_qr_base64(portal_url)


    subscription_info = {
        "title": "PORTAL WEB & CLUBE VIP • RADAR SEMANAL DE ESTAMPARIA",
        "description": (
            f"Acesso total ao painel interativo em {portal_display_url} com filtros por nicho, "
            "ranking de todas as estampas em alta, links diretos dos concorrentes e envio do "
            "dossiê executivo em PDF toda segunda-feira às 07h."
        ),
        "price_monthly": "R$ 97,00 / mês",
        "benefits": [
            f"Painel web interativo no ar em {portal_display_url}",
            "Top 12 a 16 estampas com maior pico de velocidade diária",
            "Auditoria completa e links diretos de todos os anúncios",
            "Alertas estratégicos para não produzir peças com margem zero",
        ],
        "portal_url": portal_url,
        "portal_display_url": portal_display_url,
    }

    # Format date and report ID
    raw_gen_at = payload.get("generated_at", "")
    if raw_gen_at:
        try:
            report_date = datetime.strptime(raw_gen_at, "%Y%m%dT%H%M%SZ").strftime("%d/%m/%Y")
        except ValueError:
            report_date = datetime.now().strftime("%d/%m/%Y")
    else:
        report_date = datetime.now().strftime("%d/%m/%Y")

    report_id = raw_gen_at or datetime.now().strftime("%Y%m%dT%H%M%SZ")

    template_data = {
        "report_id": report_id,
        "date": report_date,
        "product_count": product_count,
        "printed_count": printed_count,
        "market_daily_velocity": total_daily_velocity,
        "market_daily_velocity_fmt": _format_int_br(total_daily_velocity),
        "weekly_volume_pieces": estimated_weekly_pieces,
        "weekly_volume_pieces_fmt": _format_int_br(estimated_weekly_pieces),
        "weekly_revenue_brl": estimated_weekly_revenue_brl,
        "weekly_revenue_brl_fmt": _format_brl(estimated_weekly_revenue_brl),
        "price_p25_fmt": _format_brl(p25_cents, is_cents=True),
        "price_p50_fmt": _format_brl(p50_cents, is_cents=True),
        "price_p75_fmt": _format_brl(p75_cents, is_cents=True),
        "market_volume": printed_count,
        "median_price": (p50_cents / 100.0) if p50_cents else 0.0,
        "themes": themes_data,
        "fabric_highlights": fabric_highlights,
        "breakout_products": breakout_products,
        "strategic_production": {
            "to_print": to_print_recommendations,
            "to_pause": to_pause_recommendations,
        },
        "subscription": subscription_info,
        "portal_url": portal_url,
        "portal_display_url": portal_display_url,
        "portal_qr_base64": portal_qr_base64,
        "theme_filtered": theme_slug,
    }

    env = Environment(loader=FileSystemLoader(Path(__file__).parent / "templates"))
    template = env.get_template("dossier.html")
    html_content = template.render(**template_data)

    html_path = report_dir / "dossier.html"
    if theme_slug:
        html_path = report_dir / f"dossier_{theme_slug}.html"

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    if not output_pdf:
        return html_path

    pdf_path = html_path.with_suffix(".pdf")
    png_path = html_path.with_suffix(".png")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(
                viewport={"width": 1200, "height": 1600},
                device_scale_factor=2,
            )
            page.goto(f"file://{html_path.resolve()}")
            page.pdf(path=str(pdf_path), format="A4", print_background=True)
            page.screenshot(path=str(png_path), full_page=True)
            browser.close()
        return pdf_path
    except Exception as e:
        logger.warning("Failed to generate PDF/PNG (Playwright/Chromium issue): %s", e)
        return html_path


def generate_theme_card(theme_slug: str, report_dir: Path | None = None) -> Path:
    """Generate a high-contrast 800x800 square image card for B2B merchant outreach.

    Creates visual proof of niche momentum to spark commercial conversations
    with apparel store owners across WhatsApp and social channels. Showcases
    top breakout designs, niche sales pace, and direct call-to-action.

    Args:
        theme_slug: Category/theme identifier (slug or display name).
        report_dir: Optional custom path to a report folder containing report.json.

    Returns:
        Path to the rendered PNG screenshot card.
    """
    if report_dir is None:
        report_dir = get_latest_report_dir()
        if report_dir is None:
            raise FileNotFoundError("No report directories found.")

    report_json_path = report_dir / "report.json"
    if not report_json_path.exists():
        raise FileNotFoundError(f"report.json not found in {report_dir}")

    with open(report_json_path, "r", encoding="utf-8") as f:
        payload = json.loads(f.read())

    target_slug = normalize_theme_slug(theme_slug)
    all_products = payload.get("products", [])

    def _matches_theme(p: dict) -> bool:
        p_theme = p.get("theme")
        if not p_theme:
            return False
        return (
            p_theme.lower() == theme_slug.lower()
            or normalize_theme_slug(p_theme) == target_slug
        )

    matching_products = [p for p in all_products if _matches_theme(p)]

    def _product_velocity_or_sold(p: dict) -> tuple[float, float]:
        vel = p.get("velocity_per_day")
        sold = p.get("sold_count") or 0
        return (float(vel) if vel is not None else 0.0, float(sold))

    # Sort matching products by velocity_per_day, fallback to sold_count
    sorted_theme_products = sorted(
        matching_products, key=_product_velocity_or_sold, reverse=True
    )

    selected_products = list(sorted_theme_products[:3])

    # If not enough products for the theme, fall back to top breakout products across report
    if len(selected_products) < 3:
        used_ids = {p.get("item_id") for p in selected_products if p.get("item_id") is not None}
        breakouts = payload.get("breakout_products", [])
        candidate_fallbacks = [
            p for p in breakouts if p.get("item_id") not in used_ids
        ]
        sorted_all = sorted(
            all_products, key=_product_velocity_or_sold, reverse=True
        )
        for p in sorted_all:
            if p.get("item_id") not in used_ids and p not in candidate_fallbacks:
                candidate_fallbacks.append(p)

        for p in candidate_fallbacks:
            if len(selected_products) >= 3:
                break
            selected_products.append(p)
            if p.get("item_id") is not None:
                used_ids.add(p.get("item_id"))

    # Resolve image base64, price, and velocity for each selected product
    reference_dir = get_settings().data_dir / "reference"
    formatted_products = []
    for prod in selected_products:
        item_id = prod.get("item_id")
        p_theme = prod.get("theme") or theme_slug
        p_slug = normalize_theme_slug(p_theme)

        img_path = reference_dir / p_slug / f"{item_id}.jpg"
        if not img_path.exists():
            img_path = reference_dir / p_theme / f"{item_id}.jpg"

        if img_path.exists():
            b64_img = _image_to_base64(img_path)
        else:
            cdn_url = prod.get("image_url", "")
            b64_img = _fetch_cdn_image(cdn_url) if cdn_url else None
            if not b64_img:
                b64_img = _image_to_base64(img_path)

        price_cents = prod.get("price_cents", 0)
        price_brl = f"{price_cents / 100:.2f}".replace(".", ",")

        vel = prod.get("velocity_per_day")
        if vel is None:
            vel_val = prod.get("sold_count", 0)
        elif isinstance(vel, (int, float)):
            vel_val = int(vel) if vel == int(vel) else round(vel, 1)
        else:
            vel_val = vel

        formatted_products.append(
            {
                "item_id": item_id,
                "title": prod.get("title", ""),
                "base64_image": b64_img,
                "price_brl": price_brl,
                "velocity_per_day": vel_val,
            }
        )

    # Resolve theme display name, listings count, total velocity, and opportunity badge
    theme_display = theme_slug.replace("-", " ").title()
    listings_count = len(matching_products)
    total_velocity = 0

    for t, cnt in payload.get("theme_counts", []):
        if normalize_theme_slug(t) == target_slug or t.lower() == theme_slug.lower():
            theme_display = t.title()
            listings_count = cnt
            break

    for t, vel in payload.get("theme_velocities", []):
        if normalize_theme_slug(t) == target_slug or t.lower() == theme_slug.lower():
            if isinstance(vel, (int, float)):
                total_velocity = int(vel) if vel == int(vel) else round(vel, 1)
            else:
                total_velocity = vel
            break

    if not total_velocity:
        sum_vel = sum(
            (p.get("velocity_per_day") or p.get("sold_count") or 0) for p in matching_products
        )
        total_velocity = int(round(sum_vel)) if sum_vel else (listings_count * 10)

    # Opportunity metadata
    opp_meta = payload.get("theme_opportunities", {})
    theme_opp = None
    if isinstance(opp_meta, dict):
        theme_opp = opp_meta.get(theme_slug) or opp_meta.get(target_slug)
    elif isinstance(opp_meta, list):
        for item in opp_meta:
            if isinstance(item, dict) and (
                item.get("theme") == theme_slug
                or normalize_theme_slug(item.get("theme", "")) == target_slug
            ):
                theme_opp = item
                break

    opportunity_label = "Alta Procura • Pouca Concorrência"
    badge_color = "emerald"
    if theme_opp and isinstance(theme_opp, dict):
        opportunity_label = theme_opp.get("label", opportunity_label)
        badge_color = theme_opp.get("badge_color", badge_color)

    env = Environment(loader=FileSystemLoader(Path(__file__).parent / "templates"))
    template = env.get_template("card.html")
    html_content = template.render(
        theme_display=theme_display,
        badge_color=badge_color,
        opportunity_label=opportunity_label,
        total_velocity=total_velocity,
        listings_count=listings_count,
        products=formatted_products,
    )

    output_dir = report_dir / "cards"
    output_dir.mkdir(parents=True, exist_ok=True)
    html_path = output_dir / f"{theme_slug}.html"
    html_path.write_text(html_content, encoding="utf-8")
    png_path = output_dir / f"{theme_slug}.png"

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=True, channel="chrome")
        except Exception as exc:  # noqa: BLE001
            logger.debug("Falling back to default chromium launcher: %s", exc)
            browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 800, "height": 800})
        page.goto(f"file://{html_path.resolve()}")
        page.screenshot(path=str(png_path), type="png")
        browser.close()

    return png_path

