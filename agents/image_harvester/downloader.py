"""Image downloader for the Shopee CDN (plain HTTP - no browser needed)."""

import re
from pathlib import Path

import httpx

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Referer": "https://shopee.com.br/",
}


def clean_shopee_image_url(url: str) -> str:
    """Strip Shopee thumbnail suffixes and resize parameters for full resolution."""
    clean = url.split("?")[0].split("#")[0]
    clean = re.sub(r"@.*$", "", clean)
    return re.sub(r"_tn(?=\.|$)", "", clean)


def _fetch(client: httpx.Client, url: str, dest: Path, timeout: float) -> bool:
    try:
        resp = client.get(url, timeout=timeout)
        resp.raise_for_status()
    except httpx.HTTPError:
        return False
    if "image" not in resp.headers.get("content-type", ""):
        return False
    dest.write_bytes(resp.content)
    return True


def download_image(
    url: str,
    dest: Path,
    *,
    client: httpx.Client | None = None,
    timeout: float = 30.0,
) -> bool:
    """Download `url` to `dest`. Idempotent (skips existing). True on success."""
    if dest.exists():
        return True
    dest.parent.mkdir(parents=True, exist_ok=True)

    clean_url = clean_shopee_image_url(url)

    c = (
        client
        if client is not None
        else httpx.Client(headers=HEADERS, follow_redirects=True, timeout=timeout)
    )

    try:
        success = _fetch(c, clean_url, dest, timeout)
        if not success and clean_url != url:
            success = _fetch(c, url, dest, timeout)
        return success
    finally:
        if client is None:
            c.close()
