"""Dashboard smoke test (Streamlit AppTest - no browser)."""

import io
import zipfile

from streamlit.testing.v1 import AppTest

from dashboard.app import build_dossier_zip


def test_app_runs_without_exceptions(isolated) -> None:
    at = AppTest.from_file("../dashboard/app.py", default_timeout=60)
    at.run()
    assert not at.exception


def test_build_dossier_zip(isolated) -> None:
    """Verify build_dossier_zip creates a valid ZIP with a CSV and nested images."""
    # Setup mock payload and reference images
    payload = {
        "products": [
            {
                "item_id": 1,
                "theme": "memes",
                "sold_count": 100,
                "price_cents": 2500,
                "title": "A",
                "url": "U",
            }
        ]
    }

    reference_dir = isolated / "reference"
    memes_dir = reference_dir / "memes"
    memes_dir.mkdir(parents=True)
    (memes_dir / "1.jpg").write_bytes(b"image_content")

    # Call the function
    zip_bytes = build_dossier_zip("test_report", payload)
    assert isinstance(zip_bytes, bytes)

    # Read the ZIP
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        names = zf.namelist()
        assert "commercial_summary.csv" in names
        assert "images/memes/1.jpg" in names

        csv_content = zf.read("commercial_summary.csv").decode("utf-8")
        assert "item_id,theme,sold_count,price_brl,title,url" in csv_content
        assert "1,memes,100,25.0,A,U" in csv_content

        img_content = zf.read("images/memes/1.jpg")
        assert img_content == b"image_content"
