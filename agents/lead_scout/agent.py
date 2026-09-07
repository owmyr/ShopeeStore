import json
import logging
import re
import unicodedata
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import httpx
from sqlalchemy import func
from sqlmodel import Session, select

from agents.lead_scout.discovery import GOOGLEBOT_HEADERS, discover_lead
from core import ledger
from core.config import get_settings
from core.db import session_scope
from core.models import PriceSnapshot, Product, StoreLead

logger = logging.getLogger(__name__)

SLEEVE_RE = re.compile(
    r"\b(sem\s+mangas?|com\s+mangas?|mangas?\s+(?:curtas?|longas?|raglan\w*|3/4|bufantes?|princesas?|dobradas?|com\s+dobra|com\s+punho))\b",
    re.IGNORECASE,
)

ANIME_RE = re.compile(
    r"\b(animes?|otakus?|naruto|dragon\s*ball|goku|luffy|one\s*piece|attack\s*on\s*titan|"
    r"shingeki|jujutsu|kimetsu|demon\s*slayer|pokemon|cosplay|thundercats|death\s*note|"
    r"bleach|akatsuki|uchiha)\b",
    re.IGNORECASE,
)

THEME_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "religioso e cristao",
        re.compile(
            r"\b(cristo|jesus|deus|fe|gospel|biblia|biblias|cruz|cruzes|yeshua|igreja|igrejas|"
            r"oracao|oracoes|salmo|salmos|evangelic[ao]s?|versicul[ao]s?|louvor|louvores|"
            r"pastor[a]?|pastores|pastoras)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "geek e super-herois",
        re.compile(
            r"\b(heroi|herois|vingadores|avengers|batman|homem\s*aranha|spider\s*man|marvel|"
            r"dc\s*comics|star\s*wars|harry\s*potter|gamers?|playstation|xbox|nintendo)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "rock e musica",
        re.compile(
            r"\b(rock|metal|heavy\s*metal|punk|hardcore|bandas?|guitar|guitarras?|nirvana|"
            r"metallica|iron\s*maiden|ac\s*/\s*dc|acdc|cpm\s*22|beatles|kiss|ska)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "k-pop",
        re.compile(r"\b(k-?pop|bts|blackpink|stray\s*kids|army)\b", re.IGNORECASE),
    ),
    (
        "country e sertanejo",
        re.compile(
            r"\b(agro|country|cavalos?|bois?|boiadeir[ao]s?|touros?|sertanej[ao]s?|peao|peoes|"
            r"rodeios?|haras|fazendas?|vaquejadas?|brut[ao]s?|botas?)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "streetwear",
        re.compile(
            r"\b(street\s*wear|streetwear|oversizes?|oversized|skaters?|skate|quebrada|favela|"
            r"traps?|hype|rap|hip\s*hop|swag|baggy|gringa|drip|grau|maloqueir[ao]s?|mandrake|"
            r"chronic|tio\s*patinhas|irmaos\s*metralha)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "automotivo",
        re.compile(
            r"\b(motos?|motocross|harley|carros?|automotiv[ao]s?|automobilismo|drift|turbo|"
            r"formula\s*1|f1|oficinas?|motores|motor|custom\s*bike)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "desenhos e animacoes",
        re.compile(
            r"\b(garfield|garfild|snoopy|stitch|mickey|minnie|bob\s*esponja|tom\s*e\s*jerry|"
            r"simpsons|looney\s*tunes|desenhos?|rei\s*leao)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "pets e animais",
        re.compile(
            r"\b(gatos?|gatinh[ao]s?|cats?|dogs?|cachorros?|cao|caes|pets?|patinhas?|capivaras?|"
            r"pandas?|leao|leoes|tigres?|lobos?|coelhos?|animais|animal|passaros?)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "frutas e flores",
        re.compile(
            r"\b(girassol|girassois|margaridas?|flor|flores|cerejas?|cherry|morangos?|cactos?|"
            r"floral|florais|rosas?|botanical|plantas?|coracao|coracoes)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "esportes",
        re.compile(
            r"\b(futebol|academia|treino|treinos|maromba|shape|fitness|musculacao|crossfit|"
            r"basquete|corrida|corridas|jiu\s*jitsu|personal\s*trainer|neymar)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "familia",
        re.compile(
            r"\b(papai|paizao|mamae|mae|maes|filho|filha|filhos|filhas|casal|namorados?|"
            r"familias?|vovo|dindo|dia\s*dos\s*pais|dia\s*das\s*maes)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "infantil",
        re.compile(
            r"\b(infantil|infantis|criancas?|bebe|bebes|kids|mesversario|bodys?)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "politica",
        re.compile(
            r"\b(politica|lula|bolsonaro|patriotas?|eleicoes|eleicao)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "profissoes",
        re.compile(
            r"\b(professores?|professoras?|enfermeir[ao]s?|medic[ao]s?|advogad[ao]s?|"
            r"veterinari[ao]s?|barbeir[ao]s?|cabeleireir[ao]s?)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "frases engracadas",
        re.compile(
            r"\b(memes?|frases?|engracad[ao]s?|piadas?|deboches?)\b",
            re.IGNORECASE,
        ),
    ),
]


def load_latest_report(reports_dir: Path | None = None) -> tuple[Path | None, dict | None]:
    """Load the latest Trend Scout report json.

    Why: Provides access to recent theme clustering and product-level classifications
    generated by the trend scout agent to enrich merchant store themes.
    """
    if reports_dir is None:
        reports_dir = get_settings().data_dir / "reports"

    if not reports_dir.exists():
        return None, None

    dirs = sorted(d for d in reports_dir.iterdir() if d.is_dir() and (d / "report.json").exists())
    if not dirs:
        return None, None

    latest = dirs[-1]
    try:
        data = json.loads((latest / "report.json").read_text(encoding="utf-8"))
        return latest, data
    except Exception as exc:
        logger.warning("Failed to load report from %s: %s", latest, exc)
        return None, None


def build_report_theme_mappings(
    report_data: dict | None,
) -> tuple[dict[int, list[str]], dict[int, str]]:
    """Build shop and item theme lookup maps from a report payload.

    Why: Allows fast O(1) lookup of categorized themes from Trend Scout
    for shops and specific products, filtering out plain or empty entries.
    """
    if not report_data:
        return {}, {}

    shop_theme_map: dict[int, list[str]] = {}
    item_theme_map: dict[int, str] = {}

    all_items = list(report_data.get("products", [])) + list(
        report_data.get("breakout_products", [])
    )

    for item in all_items:
        theme = item.get("theme")
        if not theme or theme.strip() == "" or theme.strip() == "nao-estampada":
            continue

        clean_theme = theme.strip()
        shop_id = item.get("shop_id")
        item_id = item.get("item_id")

        if shop_id is not None:
            shop_theme_map.setdefault(shop_id, []).append(clean_theme)
        if item_id is not None:
            item_theme_map[item_id] = clean_theme

    return shop_theme_map, item_theme_map


def classify_theme_by_title(title: str) -> str:
    """Classify a product title into a standard shirt theme using regex heuristics.

    Why: When a shop or product was not classified in recent Trend Scout reports,
    this provides deterministic keyword-based theme detection without LLM calls.
    """
    if not title or not title.strip():
        return "geral / multitemas"

    # Remove diacritics / accents for robust matching
    normalized = unicodedata.normalize("NFKD", title)
    clean = "".join(c for c in normalized if not unicodedata.combining(c)).lower()

    # Disambiguate clothing sleeves (manga curta, manga longa, etc.) from manga comics
    no_sleeves = SLEEVE_RE.sub(" ", clean)

    if ANIME_RE.search(clean) or re.search(r"\bmangas?\b", no_sleeves):
        return "anime e geek"

    for theme, pattern in THEME_PATTERNS:
        if pattern.search(clean):
            return theme

    return "geral / multitemas"


def resolve_lead_theme(
    shop_id: int,
    top_product: Product | None,
    shop_theme_map: dict[int, list[str]],
    item_theme_map: dict[int, str],
) -> str:
    """Resolve the most specific theme for a store lead using a fallback hierarchy.

    Why: Ensures leads are categorized by:
    1. Majority theme among the shop's monitored products in the latest report.
    2. Theme of the shop's top product in the report.
    3. Title-based regex classification of the top product.
    4. Fallback to 'geral / multitemas' (never generic 'camisetas estampadas').
    """
    if shop_id in shop_theme_map and shop_theme_map[shop_id]:
        themes = shop_theme_map[shop_id]
        return Counter(themes).most_common(1)[0][0]
    elif top_product is not None and top_product.item_id in item_theme_map:
        return item_theme_map[top_product.item_id]
    elif top_product is not None and top_product.title:
        return classify_theme_by_title(top_product.title)
    else:
        return "geral / multitemas"


def migrate_lead_themes(
    session: Session | None = None, reports_dir: Path | None = None
) -> int:
    """Migrate all StoreLead records to updated theme classifications.

    Why: Existing database records might carry legacy placeholder values like
    'camisetas estampadas'. This iterates over all records and reclassifies them.
    """
    if session is None:
        with session_scope() as s:
            return migrate_lead_themes(session=s, reports_dir=reports_dir)

    _, report_data = load_latest_report(reports_dir=reports_dir)
    shop_theme_map, item_theme_map = build_report_theme_mappings(report_data)

    leads = session.exec(select(StoreLead)).all()
    migrated_count = 0

    for lead in leads:
        top_product_query = (
            select(Product, func.max(PriceSnapshot.sold_count))
            .join(PriceSnapshot, Product.id == PriceSnapshot.product_id, isouter=True)
            .where(Product.shop_id == lead.shop_id)
            .group_by(Product.id)
            .order_by(func.max(PriceSnapshot.sold_count).desc(), Product.first_seen_at)
            .limit(1)
        )
        result = session.exec(top_product_query).first()
        top_product = result[0] if result else None

        if top_product is None and lead.top_product_title:
            top_product = Product(
                item_id=0,
                shop_id=lead.shop_id,
                title=lead.top_product_title,
                url="",
                first_seen_at=datetime.now(UTC),
                last_seen_at=datetime.now(UTC),
            )

        new_theme = resolve_lead_theme(
            lead.shop_id, top_product, shop_theme_map, item_theme_map
        )
        lead.top_theme = new_theme
        session.add(lead)
        migrated_count += 1

    session.commit()
    return migrated_count


def run_once(
    max_shops: int = 50, enrich_cnpj: bool = True, client: httpx.Client | None = None
) -> int:
    """Run the lead scout agent to discover and enrich store leads."""
    processed_count = 0
    should_close_client = False
    if client is None:
        client = httpx.Client(
            headers=GOOGLEBOT_HEADERS,
            follow_redirects=True,
            timeout=10.0,
        )
        should_close_client = True

    try:
        _, report_data = load_latest_report()
        shop_theme_map, item_theme_map = build_report_theme_mappings(report_data)

        with ledger.run("lead_scout") as handle:
            with session_scope() as session:
                # Query shops ordered by sold volume and freshness
                shop_query = (
                    select(
                        Product.shop_id,
                        func.max(Product.shop_name),
                    )
                    .join(PriceSnapshot, Product.id == PriceSnapshot.product_id, isouter=True)
                    .group_by(Product.shop_id)
                    .order_by(
                        func.coalesce(func.max(PriceSnapshot.sold_count), 0).desc(),
                        func.max(PriceSnapshot.captured_at).desc(),
                    )
                    .limit(max_shops)
                )
                shops = session.exec(shop_query).all()

                for shop_id, shop_name in shops:
                    # Find top product for the shop
                    top_product_query = (
                        select(Product, func.max(PriceSnapshot.sold_count))
                        .join(PriceSnapshot, Product.id == PriceSnapshot.product_id, isouter=True)
                        .where(Product.shop_id == shop_id)
                        .group_by(Product.id)
                        .order_by(func.max(PriceSnapshot.sold_count).desc(), Product.first_seen_at)
                        .limit(1)
                    )

                    result = session.exec(top_product_query).first()
                    if not result:
                        continue

                    top_product = result[0]

                    enriched_lead = discover_lead(
                        shop_id=shop_id,
                        shop_name=shop_name,
                        top_product=top_product,
                        session=session,
                        client=client,
                        enrich_cnpj=enrich_cnpj,
                    )

                    lead_theme = resolve_lead_theme(
                        shop_id, top_product, shop_theme_map, item_theme_map
                    )

                    # Check if StoreLead exists
                    lead_query = select(StoreLead).where(StoreLead.shop_id == shop_id)
                    existing_lead = session.exec(lead_query).first()

                    now = datetime.now(UTC)
                    shop_url = f"https://shopee.com.br/shop/{shop_id}"

                    if existing_lead:
                        existing_lead.top_product_title = enriched_lead.top_product_title
                        if not existing_lead.shop_name or existing_lead.shop_name.startswith(
                            "Loja #"
                        ):
                            existing_lead.shop_name = enriched_lead.shop_name

                        if not existing_lead.shop_url:
                            existing_lead.shop_url = shop_url
                        if (
                            not existing_lead.top_theme
                            or existing_lead.top_theme == "camisetas estampadas"
                        ):
                            existing_lead.top_theme = lead_theme

                        if enriched_lead.instagram and not existing_lead.instagram:
                            existing_lead.instagram = enriched_lead.instagram
                        if enriched_lead.email and not existing_lead.email:
                            existing_lead.email = enriched_lead.email
                        if enriched_lead.cnpj and not existing_lead.cnpj:
                            existing_lead.cnpj = enriched_lead.cnpj
                        if enriched_lead.razao_social and not existing_lead.razao_social:
                            existing_lead.razao_social = enriched_lead.razao_social
                        if enriched_lead.nome_fantasia and not existing_lead.nome_fantasia:
                            existing_lead.nome_fantasia = enriched_lead.nome_fantasia
                        if enriched_lead.city and not existing_lead.city:
                            existing_lead.city = enriched_lead.city
                        if enriched_lead.state and not existing_lead.state:
                            existing_lead.state = enriched_lead.state

                        if enriched_lead.cnpj and enrich_cnpj:
                            existing_lead.enriched_at = now

                        session.add(existing_lead)
                    else:
                        new_lead = StoreLead(
                            shop_id=shop_id,
                            shop_name=enriched_lead.shop_name,
                            shop_url=shop_url,
                            instagram=enriched_lead.instagram,
                            email=enriched_lead.email,
                            cnpj=enriched_lead.cnpj,
                            razao_social=enriched_lead.razao_social,
                            nome_fantasia=enriched_lead.nome_fantasia,
                            city=enriched_lead.city,
                            state=enriched_lead.state,
                            status="discovered",
                            top_theme=lead_theme,
                            top_product_title=enriched_lead.top_product_title,
                            discovered_at=now,
                            enriched_at=now if (enriched_lead.cnpj and enrich_cnpj) else None,
                            run_id=handle.run_id,
                        )
                        session.add(new_lead)

                    processed_count += 1

                session.commit()
    finally:
        if should_close_client:
            client.close()

    return processed_count
