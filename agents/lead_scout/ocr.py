import logging
import re
import subprocess
import tempfile
from collections import Counter
from pathlib import Path

from PIL import Image
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


def extract_watermark_handles(image_path: Path) -> list[str]:
    """
    Scan peripheral crops of an image and return unique candidate Instagram handles.

    Why: Top apparel sellers on Shopee Brazil place their brand logos or @handles along
    the margins and corners of mockup photos to prevent image theft. Cropping the perimeter
    avoids OCR confusion with the actual graphic illustration printed on the t-shirt chest.
    """
    handles = set()
    try:
        with Image.open(image_path) as img:
            width, height = img.size

            # Define crops: top 15%, bottom 25%, left 15%, right 15%
            crops = [
                img.crop((0, 0, width, int(height * 0.15))),  # Top
                img.crop((0, int(height * 0.75), width, height)),  # Bottom
                img.crop((0, 0, int(width * 0.15), height)),  # Left
                img.crop((int(width * 0.85), 0, width, height)),  # Right
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
                    text = result.stdout

                    matches = re.findall(
                        r"(?:@|insta(?:gram)?[:\s]+)([a-zA-Z0-9._]{3,30})", text, re.IGNORECASE
                    )
                    for match in matches:
                        handle = match.lower().rstrip(".")
                        if handle and not any(stopword in handle for stopword in STOPWORDS):
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
    """
    Scan harvested reference images for a shop and return the most frequent watermark handle.

    Why: Cross-referencing multiple product photos from the same merchant filters out random
    OCR noise or false positives, ensuring only repeated brand handles are attributed.
    """
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

        # Search recursively in case images are grouped under theme subfolders
        matches = list(reference_dir.glob(f"**/{product.item_id}.jpg"))
        if matches:
            handles = extract_watermark_handles(matches[0])
            all_handles.extend(handles)
            scanned_count += 1

    if not all_handles:
        return None

    counter = Counter(all_handles)
    most_common, count = counter.most_common(1)[0]
    return most_common
