import tempfile
from datetime import UTC, datetime
from pathlib import Path

import pytest
from PIL import Image
from sqlmodel import Session, SQLModel, create_engine

from agents.lead_scout.discovery import extract_watermark_handles, scan_shop_reference_images
from core.models import Product


@pytest.fixture
def test_db():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_extract_watermark_handles_regex(monkeypatch):
    class MockResult:
        def __init__(self, stdout):
            self.stdout = stdout

    mocked_texts = [
        "Some text @use.marca more text",
        "insta: my_brand and something",
        "instagram: loja.top. ignoring trailing dot",
        "Stopwords @shopee @camiseta @use.shopee but valid @valid_brand",
    ]

    call_count = 0

    def mock_run(*args, **kwargs):
        nonlocal call_count
        stdout = mocked_texts[call_count % len(mocked_texts)]
        call_count += 1
        return MockResult(stdout)

    monkeypatch.setattr("agents.lead_scout.discovery.subprocess.run", mock_run)

    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tf:
        img = Image.new("RGB", (100, 100), color="white")
        img.save(tf.name)
        img_path = Path(tf.name)

    try:
        handles = extract_watermark_handles(img_path)
        assert "use.marca" in handles
        assert "my_brand" in handles
        assert "loja.top" in handles
        assert "valid_brand" in handles
        assert "shopee" not in handles
        assert "camiseta" not in handles
        assert "use.shopee" not in handles
    finally:
        img_path.unlink(missing_ok=True)


def test_scan_shop_reference_images(test_db, monkeypatch, tmp_path):
    now = datetime.now(UTC)
    test_db.add(
        Product(
            id=1,
            shop_id=10,
            item_id=1001,
            shop_name="Test",
            title="T1",
            price=100,
            original_price=100,
            url="http",
            image_url="http",
            first_seen_at=now,
            last_seen_at=now,
        )
    )
    test_db.add(
        Product(
            id=2,
            shop_id=10,
            item_id=1002,
            shop_name="Test",
            title="T2",
            price=100,
            original_price=100,
            url="http",
            image_url="http",
            first_seen_at=now,
            last_seen_at=now,
        )
    )
    test_db.commit()

    img1 = tmp_path / "1001.jpg"
    img2 = tmp_path / "1002.jpg"
    Image.new("RGB", (100, 100)).save(img1)
    Image.new("RGB", (100, 100)).save(img2)

    def mock_extract(path):
        if path.name == "1001.jpg":
            return ["marca1", "marca_top"]
        if path.name == "1002.jpg":
            return ["marca1"]
        return []

    monkeypatch.setattr("agents.lead_scout.discovery.extract_watermark_handles", mock_extract)

    handle = scan_shop_reference_images(10, test_db, tmp_path)
    assert handle == "marca1"
