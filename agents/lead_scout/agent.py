import logging
from datetime import UTC, datetime

import httpx
from sqlalchemy import func
from sqlmodel import select

from agents.lead_scout.discovery import GOOGLEBOT_HEADERS, discover_lead
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

                    enriched_lead = discover_lead(
                        shop_id=shop_id,
                        shop_name=shop_name,
                        top_product=top_product,
                        session=session,
                        client=client,
                        enrich_cnpj=enrich_cnpj,
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
                        if not existing_lead.top_theme:
                            existing_lead.top_theme = "camisetas estampadas"

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
                            top_theme="camisetas estampadas",
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
