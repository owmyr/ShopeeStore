"""Image Harvester tests (HTTP + LLM faked)."""

import json
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from sqlmodel import select

from agents.image_harvester import agent as harvester
from agents.image_harvester.downloader import download_image
from core import db
from core.config import get_settings
from core.models import AgentLedger, Product, ProductImage


@pytest.fixture()
def isolated(tmp_path, monkeypatch) -> Iterator:
    monkeypatch.setenv("DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setenv("LEDGER_PATH", str(tmp_path / "ledger.jsonl"))
    get_settings.cache_clear()
    db.reset_engine()
    db.init_db()
    yield tmp_path
    db.reset_engine()
    get_settings.cache_clear()


class TestDownloadImage:
    def test_success_writes_file(self, tmp_path) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200, content=b"\xff\xd8img", headers={"content-type": "image/jpeg"}
            )

        client = httpx.Client(transport=httpx.MockTransport(handler))
        dest = tmp_path / "x.jpg"
        assert download_image("https://cdn/x.jpg", dest, client=client) is True
        assert dest.read_bytes() == b"\xff\xd8img"

    def test_skips_existing(self, tmp_path) -> None:
        dest = tmp_path / "x.jpg"
        dest.write_bytes(b"old")

        def handler(request):
            raise AssertionError("should not be called")

        client = httpx.Client(transport=httpx.MockTransport(handler))
        assert download_image("https://cdn/x.jpg", dest, client=client) is True
        assert dest.read_bytes() == b"old"

    def test_rejects_non_image_content_type(self, tmp_path) -> None:
        client = httpx.Client(
            transport=httpx.MockTransport(
                lambda r: httpx.Response(
                    200, content=b"<html>", headers={"content-type": "text/html"}
                )
            )
        )
        dest = tmp_path / "x.jpg"
        assert download_image("https://cdn/x", dest, client=client) is False
        assert not dest.exists()

    def test_http_error_returns_false(self, tmp_path) -> None:
        client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(403)))
        assert download_image("https://cdn/x.jpg", tmp_path / "x.jpg", client=client) is False


def _seed(tmp_path: Path, monkeypatch) -> None:
    """Product rows in DB + a report.json on disk."""
    now = datetime.now(UTC).replace(tzinfo=None)
    with db.session_scope() as s:
        s.add(Product(item_id=1, shop_id=10, title="camiseta meme", url="u1",
                      image_url="https://cdn/1.jpg", first_seen_at=now, last_seen_at=now))
        s.add(Product(item_id=2, shop_id=10, title="camiseta caveira premium", url="u2",
                      image_url="https://cdn/2.jpg", first_seen_at=now, last_seen_at=now))
        s.commit()

    report_dir = tmp_path / "reports" / "20260727T000000Z"
    report_dir.mkdir(parents=True)
    (report_dir / "report.json").write_text(
        json.dumps({
            "generated_at": "20260727T000000Z",
            "product_count": 2,
            "price_p25_cents": 0, "price_p50_cents": 0, "price_p75_cents": 0,
            "theme_counts": [["memes", 1]],
            "products": [
                {"item_id": 1, "shop_id": 10, "title": "camiseta meme", "url": "u1",
                 "price_cents": 3000, "sold_count": 500, "rating": 4.8, "theme": "memes"},
                {"item_id": 2, "shop_id": 10, "title": "camiseta caveira premium", "url": "u2",
                 "price_cents": 2000, "sold_count": 900, "rating": None, "theme": None},
            ],
        }),
        encoding="utf-8",
    )


def test_run_once_downloads_and_records(isolated, monkeypatch) -> None:
    _seed(isolated, monkeypatch)

    def fake_download(url: str, dest: Path, **_kwargs) -> bool:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"img")
        return True

    monkeypatch.setattr(harvester, "download_image", fake_download)

    out = harvester.run_once(max_images=10)

    assert out == isolated / "reference"
    assert (isolated / "reference" / "memes" / "1.jpg").exists()
    assert (isolated / "reference" / "sem-tema" / "2.jpg").exists()

    with db.session_scope() as s:
        rows = list(s.exec(select(ProductImage)).all())
        runs = list(s.exec(select(AgentLedger)).all())

    assert len(rows) == 2
    themes = {r.theme for r in rows}
    assert themes == {"memes", ""}
    assert len(runs) == 1 and runs[0].agent == "image_harvester"
    assert runs[0].status == "success"


def test_run_once_skips_plain_and_nao_estampada(isolated, monkeypatch) -> None:
    now = datetime.now(UTC).replace(tzinfo=None)
    with db.session_scope() as s:
        s.add(Product(item_id=1, shop_id=10, title="Camiseta Basica Lisa", url="u1",
                      image_url="https://cdn/1.jpg", first_seen_at=now, last_seen_at=now))
        s.add(Product(item_id=2, shop_id=10, title="Camiseta Premium Conforto", url="u2",
                      image_url="https://cdn/2.jpg", first_seen_at=now, last_seen_at=now))
        s.add(Product(item_id=3, shop_id=10, title="Camiseta Caveira Tribal", url="u3",
                      image_url="https://cdn/3.jpg", first_seen_at=now, last_seen_at=now))
        s.commit()

    report_dir = isolated / "reports" / "20260727T000000Z"
    report_dir.mkdir(parents=True)
    (report_dir / "report.json").write_text(
        json.dumps({
            "generated_at": "20260727T000000Z",
            "product_count": 3,
            "price_p25_cents": 0, "price_p50_cents": 0, "price_p75_cents": 0,
            "theme_counts": [],
            "products": [
                {"item_id": 1, "shop_id": 10, "title": "Camiseta Basica Lisa", "url": "u1",
                 "price_cents": 3000, "sold_count": 900, "rating": None, "theme": None},
                {"item_id": 2, "shop_id": 10, "title": "Camiseta Premium Conforto", "url": "u2",
                 "price_cents": 3000, "sold_count": 500, "rating": None, "theme": "nao-estampada"},
                {"item_id": 3, "shop_id": 10, "title": "Camiseta Caveira Tribal", "url": "u3",
                 "price_cents": 3000, "sold_count": 100, "rating": None, "theme": "caveira"},
            ],
        }),
        encoding="utf-8",
    )

    def fake_download(url: str, dest: Path, **_kwargs) -> bool:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"img")
        return True

    monkeypatch.setattr(harvester, "download_image", fake_download)

    harvester.run_once(max_images=10)

    # only the printed caveira shirt lands in reference/
    jpgs = list((isolated / "reference").rglob("*.jpg"))
    assert len(jpgs) == 1
    assert jpgs[0].parent.name == "caveira"
    assert jpgs[0].name == "3.jpg"


def test_run_once_requires_report(isolated) -> None:
    with pytest.raises(RuntimeError, match="trend_scout"):
        harvester.run_once()
