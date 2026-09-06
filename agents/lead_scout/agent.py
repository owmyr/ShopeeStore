import logging
from datetime import UTC, datetime

import httpx
from sqlalchemy import func
from sqlmodel import select

from agents.lead_scout.enricher import (
    GOOGLEBOT_HEADERS,
    fetch_shopee_shop_metadata,
)
from agents.lead_scout.enricher import (
    enrich_cnpj as do_enrich_cnpj,
)
from agents.lead_scout.extractor import extract_cnpj, extract_email, extract_instagram
from agents.lead_scout.ocr import scan_shop_reference_images
from core import ledger
from core.db import session_scope
from core.models import PriceSnapshot, Product, StoreLead

logger = logging.getLogger(__name__)


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
        with ledger.run("lead_scout") as handle:
            with session_scope() as session:
                # Query unique shops from Product
                shop_query = (
                    select(Product.shop_id, Product.shop_name)
                    .group_by(Product.shop_id, Product.shop_name)
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

                    # Query public shop metadata (brand name and bio) from Shopee
                    shop_meta = fetch_shopee_shop_metadata(shop_id, client=client)
                    real_name = shop_meta.get("shop_name") or shop_name
                    bio_desc = shop_meta.get("description") or ""

                    # Extract text
                    text_corpus = f"{real_name} {bio_desc} {top_product.title}"

                    cnpj = shop_meta.get("cnpj") or extract_cnpj(text_corpus)
                    email = shop_meta.get("email") or extract_email(text_corpus)
                    instagram = shop_meta.get("instagram") or extract_instagram(text_corpus)
                    if not instagram:
                        instagram = scan_shop_reference_images(shop_id, session)

                    razao_social = None
                    nome_fantasia = None
                    city = None
                    state = None

                    if cnpj and enrich_cnpj:
                        enriched = do_enrich_cnpj(cnpj, client)
                        if enriched:
                            razao_social = enriched.get("razao_social")
                            nome_fantasia = enriched.get("nome_fantasia")
                            email = email or enriched.get("email")
                            city = enriched.get("city")
                            state = enriched.get("state")

                    # Check if StoreLead exists
                    lead_query = select(StoreLead).where(StoreLead.shop_id == shop_id)
                    existing_lead = session.exec(lead_query).first()

                    now = datetime.now(UTC)

                    effective_shop_name = (real_name or "").strip() or f"Loja #{shop_id}"
                    shop_url = f"https://shopee.com.br/shop/{shop_id}"

                    if existing_lead:
                        existing_lead.top_product_title = top_product.title
                        if real_name and (
                            not existing_lead.shop_name
                            or existing_lead.shop_name.startswith("Loja #")
                        ):
                            existing_lead.shop_name = real_name
                        elif not existing_lead.shop_name:
                            existing_lead.shop_name = effective_shop_name

                        if not existing_lead.shop_url:
                            existing_lead.shop_url = shop_url
                        if not existing_lead.top_theme:
                            existing_lead.top_theme = "camisetas estampadas"

                        if instagram and not existing_lead.instagram:
                            existing_lead.instagram = instagram
                        if email and not existing_lead.email:
                            existing_lead.email = email
                        if cnpj and not existing_lead.cnpj:
                            existing_lead.cnpj = cnpj
                        if razao_social and not existing_lead.razao_social:
                            existing_lead.razao_social = razao_social
                        if nome_fantasia and not existing_lead.nome_fantasia:
                            existing_lead.nome_fantasia = nome_fantasia
                        if city and not existing_lead.city:
                            existing_lead.city = city
                        if state and not existing_lead.state:
                            existing_lead.state = state

                        if cnpj and enrich_cnpj:
                            existing_lead.enriched_at = now

                        session.add(existing_lead)
                    else:
                        new_lead = StoreLead(
                            shop_id=shop_id,
                            shop_name=effective_shop_name,
                            shop_url=shop_url,
                            instagram=instagram,
                            email=email,
                            cnpj=cnpj,
                            razao_social=razao_social,
                            nome_fantasia=nome_fantasia,
                            city=city,
                            state=state,
                            status="discovered",
                            top_theme="camisetas estampadas",
                            top_product_title=top_product.title,
                            discovered_at=now,
                            enriched_at=now if (cnpj and enrich_cnpj) else None,
                            run_id=handle.run_id,
                        )
                        session.add(new_lead)

                    processed_count += 1

                session.commit()
    finally:
        if should_close_client:
            client.close()

    return processed_count
