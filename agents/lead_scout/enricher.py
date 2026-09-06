import html
import logging
import re
import unicodedata
import urllib.parse
from typing import Any

import httpx

from agents.lead_scout.extractor import extract_cnpj, extract_email, extract_instagram

logger = logging.getLogger(__name__)

GOOGLEBOT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

DDG_DESKTOP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

RESERVED_IG_SLUGS = {
    "p",
    "reel",
    "reels",
    "explore",
    "stories",
    "direct",
    "accounts",
    "about",
    "developer",
    "terms",
    "privacy",
}


def verify_instagram_handle(
    handle: str, client: httpx.Client | None = None
) -> tuple[bool, str | None]:
    """Verify if an Instagram handle actually exists and return its display name."""
    if not handle or len(handle) < 3:
        return False, None

    clean = handle.lstrip("@").strip().lower()
    if clean in RESERVED_IG_SLUGS or clean.isdigit():
        return False, None

    should_close = False
    if client is None:
        client = httpx.Client(headers=GOOGLEBOT_HEADERS, follow_redirects=True, timeout=8.0)
        should_close = True

    try:
        url = f"https://www.instagram.com/{clean}/"
        response = client.get(url, headers=GOOGLEBOT_HEADERS)
        if response.status_code != 200:
            return False, None

        og = re.findall(
            r"<meta[^>]*property=[\"\']og:title[\"\'][^>]*content=[\"\']([^\"\']*)[\"\']",
            response.text,
        )
        if og:
            title_text = html.unescape(og[0])
            # Valid profile og:title format: 'Display Name (@handle) • Instagram photos and videos'
            if f"@{clean}" in title_text.lower():
                display_name = title_text.split("(")[0].strip()
                return True, display_name
        return False, None
    except Exception as e:
        logger.debug("Failed to verify Instagram handle %s: %e", clean, e)
        return False, None
    finally:
        if should_close:
            client.close()


def is_store_name_match(shop_name: str, profile_name: str, handle: str) -> bool:
    """Verify that an Instagram profile name/handle matches the merchant's business name."""

    def norm(s: str) -> str:
        deaccented = unicodedata.normalize("NFKD", s).encode("ASCII", "ignore").decode("utf-8")
        return re.sub(r"[^a-z0-9]", "", deaccented.lower())

    norm_shop = norm(shop_name)
    norm_profile = norm(profile_name)
    norm_handle = norm(handle)

    if not norm_shop:
        return False

    # Check substring containment
    if len(norm_shop) >= 3 and (
        norm_shop in norm_profile
        or norm_profile in norm_shop
        or norm_shop in norm_handle
        or norm_handle in norm_shop
    ):
        return True

    # Check word token overlap (e.g. "emporio" + "camisetas")
    shop_tokens = {norm(t) for t in shop_name.split() if len(t) >= 3}
    profile_tokens = {norm(t) for t in profile_name.split() if len(t) >= 3}
    if shop_tokens and profile_tokens:
        overlap = shop_tokens & profile_tokens
        if len(overlap) >= min(len(shop_tokens), 2):
            return True

    return False


def search_verified_instagram(shop_name: str, client: httpx.Client | None = None) -> str | None:
    """Search DuckDuckGo for store Instagram profiles and verify match."""
    if not shop_name or shop_name.startswith("Loja #"):
        return None

    query = f'"{shop_name}" instagram'
    url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"

    should_close = False
    if client is None:
        client = httpx.Client(timeout=10.0)
        should_close = True

    try:
        r = client.get(url, headers=DDG_DESKTOP_HEADERS)
        urls = re.findall(r"<a class=\"result__url\"[^>]*href=\"([^\"]*)\"", r.text)
        candidates: list[str] = []
        for u in urls:
            m = re.search(r"uddg=([^&]+)", u)
            if m:
                decoded = urllib.parse.unquote(m.group(1))
                match_handle = re.search(r"instagram\.com/([a-zA-Z0-9._]+)/?", decoded)
                if match_handle:
                    h = match_handle.group(1).lower()
                    if h not in RESERVED_IG_SLUGS and h not in candidates:
                        candidates.append(h)

        for cand in candidates[:5]:
            is_valid, profile_name = verify_instagram_handle(cand, client)
            if is_valid and profile_name and is_store_name_match(shop_name, profile_name, cand):
                return cand
    except Exception as e:
        logger.debug("Failed to search Instagram for %s: %s", shop_name, e)
    finally:
        if should_close:
            client.close()

    return None


def fetch_shopee_shop_metadata(shop_id: int, client: httpx.Client | None = None) -> dict[str, Any]:
    """Fetch public shop metadata (brand name and bio) from Shopee SSR."""
    should_close = False
    if client is None:
        client = httpx.Client(headers=GOOGLEBOT_HEADERS, follow_redirects=True, timeout=10.0)
        should_close = True

    url = f"https://shopee.com.br/shop/{shop_id}"
    try:
        response = client.get(url, headers=GOOGLEBOT_HEADERS)
        if response.status_code != 200:
            return {}

        og_title = re.findall(
            r"<meta[^>]*property=[\"\']og:title[\"\'][^>]*content=[\"\']([^\"\']*)[\"\']",
            response.text,
        )
        og_desc = re.findall(
            r"<meta[^>]*property=[\"\']og:description[\"\'][^>]*content=[\"\']([^\"\']*)[\"\']",
            response.text,
        )

        name = ""
        if og_title:
            clean_title = html.unescape(og_title[0]).replace("\xa0", " ")
            name = clean_title.split(", Loja Online")[0].split(" | Shopee")[0].strip()

        desc = html.unescape(og_desc[0]) if og_desc else ""

        cnpj = extract_cnpj(desc)
        email = extract_email(desc)
        bio_instagram = extract_instagram(desc)

        verified_instagram = None
        if bio_instagram:
            is_valid, _ = verify_instagram_handle(bio_instagram, client)
            if is_valid:
                verified_instagram = bio_instagram

        return {
            "shop_name": name or None,
            "description": desc or None,
            "cnpj": cnpj,
            "email": email,
            "instagram": verified_instagram,
        }
    except Exception as e:
        logger.warning("Failed to fetch shop metadata for %s: %s", shop_id, e)
        return {}
    finally:
        if should_close:
            client.close()


def enrich_cnpj(cnpj: str, client: httpx.Client | None = None) -> dict[str, Any] | None:
    """Enrich a CNPJ using Brasil API."""
    should_close = False
    if client is None:
        client = httpx.Client(timeout=10.0)
        should_close = True

    try:
        response = client.get(f"https://brasilapi.com.br/api/cnpj/v1/{cnpj}")
        if response.status_code == 200:
            data = response.json()
            return {
                "razao_social": data.get("razao_social"),
                "nome_fantasia": data.get("nome_fantasia"),
                "email": data.get("email", "").lower() if data.get("email") else None,
                "city": data.get("municipio"),
                "state": data.get("uf"),
            }
        elif response.status_code in (404, 400):
            return None
        response.raise_for_status()
    except Exception as e:
        logger.warning(f"Failed to enrich CNPJ {cnpj}: {e}")
        return None
    finally:
        if should_close:
            client.close()

    return None
