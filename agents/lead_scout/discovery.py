import html
import logging
import re
import subprocess
import tempfile
import unicodedata
import urllib.parse
from collections import Counter
from pathlib import Path
from typing import Any

import httpx
from PIL import Image
from pydantic import BaseModel
from sqlmodel import Session, select

from core.models import Product

logger = logging.getLogger(__name__)

STOPWORDS = {
    "shopee",
    "brasil",
    "estampa",
    "camiseta",
    "tamanho",
    "confeccao",
    "algodao",
    "frete",
    "envio",
    "masculina",
    "feminina",
}

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


class EnrichedLead(BaseModel):
    shop_id: int
    shop_name: str
    cnpj: str | None = None
    razao_social: str | None = None
    nome_fantasia: str | None = None
    email: str | None = None
    instagram: str | None = None
    city: str | None = None
    state: str | None = None
    top_theme: str | None = None
    top_product_title: str | None = None


def is_valid_cnpj(cnpj: str) -> bool:
    digits = re.sub(r"\D", "", cnpj)
    if len(digits) != 14:
        return False
    if len(set(digits)) == 1:
        return False

    def calculate_digit(cpf_cnpj: str, weights: list[int]) -> int:
        s = sum(int(d) * w for d, w in zip(cpf_cnpj, weights))
        r = s % 11
        return 0 if r < 2 else 11 - r

    w1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    w2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]

    d1 = calculate_digit(digits[:12], w1)
    if int(digits[12]) != d1:
        return False

    d2 = calculate_digit(digits[:13], w2)
    if int(digits[13]) != d2:
        return False

    return True


def extract_cnpj(text: str) -> str | None:
    pattern = r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b"
    matches = re.findall(pattern, text)
    for match in matches:
        digits = re.sub(r"\D", "", match)
        if is_valid_cnpj(digits):
            return digits
    return None


def extract_instagram(text: str) -> str | None:
    pattern = r"(?<![a-zA-Z0-9._%+-])@([a-zA-Z0-9._]{3,30})|instagram\.com/([a-zA-Z0-9._]{3,30})"
    for m in re.finditer(pattern, text):
        handle = m.group(1) or m.group(2)
        if handle:
            if handle.lower() in {"gmail", "hotmail", "outlook", "yahoo", "uol", "bol"}:
                continue
            if handle.lower().endswith((".com", ".com.br")):
                continue
            return handle
    return None


def extract_email(text: str) -> str | None:
    pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
    for match in re.findall(pattern, text):
        email = match.lower()
        if "example@" in email or email.endswith("@shopee.com"):
            continue
        return match
    return None


def extract_watermark_handles(image_path: Path) -> list[str]:
    handles = set()
    try:
        with Image.open(image_path) as img:
            width, height = img.size
            crops = [
                img.crop((0, 0, width, int(height * 0.15))),
                img.crop((0, int(height * 0.75), width, height)),
                img.crop((0, 0, int(width * 0.15), height)),
                img.crop((int(width * 0.85), 0, width, height)),
            ]

            for crop_img in crops:
                with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as temp_file:
                    temp_path = temp_file.name
                    crop_img.save(temp_path)

                try:
                    result = subprocess.run(
                        ["tesseract", temp_path, "stdout", "--psm", "11", "-l", "por+eng"],
                        capture_output=True,
                        text=True,
                        timeout=10,
                        check=True,
                    )
                    matches = re.findall(
                        r"(?:@|insta(?:gram)?[:\s]+)([a-zA-Z0-9._]{3,30})",
                        result.stdout,
                        re.IGNORECASE,
                    )
                    for match in matches:
                        handle = match.lower().rstrip(".")
                        if handle and not any(sw in handle for sw in STOPWORDS):
                            handles.add(handle)
                except (subprocess.SubprocessError, FileNotFoundError) as e:
                    logger.warning(f"Tesseract failed or unavailable: {e}")
                finally:
                    Path(temp_path).unlink(missing_ok=True)
    except Exception as e:
        logger.warning(f"Failed to process image {image_path}: {e}")
    return list(handles)


def scan_shop_reference_images(
    shop_id: int, session: Session, reference_dir: Path | None = None
) -> str | None:
    if reference_dir is None:
        reference_dir = Path("data/reference")
    if not reference_dir.exists():
        return None

    query = select(Product).where(Product.shop_id == shop_id).limit(50)
    products = session.exec(query).all()
    scanned_count = 0
    all_handles = []

    for product in products:
        if scanned_count >= 5:
            break
        matches = list(reference_dir.glob(f"**/{product.item_id}.jpg"))
        if matches:
            all_handles.extend(extract_watermark_handles(matches[0]))
            scanned_count += 1

    if not all_handles:
        return None

    counter = Counter(all_handles)
    most_common, _ = counter.most_common(1)[0]
    return most_common


def verify_instagram_handle(
    handle: str, client: httpx.Client | None = None
) -> tuple[bool, str | None]:
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
    def norm(s: str) -> str:
        deaccented = unicodedata.normalize("NFKD", s).encode("ASCII", "ignore").decode("utf-8")
        return re.sub(r"[^a-z0-9]", "", deaccented.lower())

    norm_shop = norm(shop_name)
    norm_profile = norm(profile_name)
    norm_handle = norm(handle)
    if not norm_shop:
        return False
    if len(norm_shop) >= 3 and (
        norm_shop in norm_profile
        or norm_profile in norm_shop
        or norm_shop in norm_handle
        or norm_handle in norm_shop
    ):
        return True
    shop_tokens = {norm(t) for t in shop_name.split() if len(t) >= 3}
    profile_tokens = {norm(t) for t in profile_name.split() if len(t) >= 3}
    if shop_tokens and profile_tokens:
        overlap = shop_tokens & profile_tokens
        if len(overlap) >= min(len(shop_tokens), 2):
            return True
    return False


def search_verified_instagram(shop_name: str, client: httpx.Client | None = None) -> str | None:
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
        candidates = []
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


def _enrich_cnpj(cnpj: str, client: httpx.Client | None = None) -> dict[str, Any] | None:
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


def discover_lead(
    shop_id: int,
    shop_name: str,
    top_product: Product,
    session: Session,
    client: httpx.Client,
    *,
    enrich_cnpj: bool = True,
    reference_dir: Path | None = None,
) -> EnrichedLead:
    """
    Coordinates the 3-tier discovery:
    1. SSR metadata / bio text
    2. Regex extraction
    3. Reference image watermark OCR fallback
    4. BrasilAPI corporate enrichment (if CNPJ present and enrich_cnpj=True)
    """
    shop_meta = fetch_shopee_shop_metadata(shop_id, client=client)
    real_name = shop_meta.get("shop_name") or shop_name
    bio_desc = shop_meta.get("description") or ""

    text_corpus = f"{real_name} {bio_desc} {top_product.title}"
    cnpj = shop_meta.get("cnpj") or extract_cnpj(text_corpus)
    email = shop_meta.get("email") or extract_email(text_corpus)
    instagram = shop_meta.get("instagram") or extract_instagram(text_corpus)

    if not instagram:
        instagram = scan_shop_reference_images(shop_id, session, reference_dir)

    razao_social = None
    nome_fantasia = None
    city = None
    state = None

    if cnpj and enrich_cnpj:
        enriched = _enrich_cnpj(cnpj, client)
        if enriched:
            razao_social = enriched.get("razao_social")
            nome_fantasia = enriched.get("nome_fantasia")
            email = email or enriched.get("email")
            city = enriched.get("city")
            state = enriched.get("state")

    return EnrichedLead(
        shop_id=shop_id,
        shop_name=real_name.strip() or f"Loja #{shop_id}",
        cnpj=cnpj,
        razao_social=razao_social,
        nome_fantasia=nome_fantasia,
        email=email,
        instagram=instagram,
        city=city,
        state=state,
        top_product_title=top_product.title,
    )
