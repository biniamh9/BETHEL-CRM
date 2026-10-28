"""Shared validation and optimization for every portal image upload."""

from io import BytesIO
from pathlib import Path
import re

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_IMAGE_BYTES = 950 * 1024
MAX_IMAGE_EDGE = 2400


class ImageProcessingError(ValueError):
    pass


def automatic_caption(filename, album_title="", position=None):
    stem = Path(filename).stem
    generic = re.fullmatch(r"(?:img|dsc|dscn|pxl|photo|image)[-_ ]?\d+", stem, re.IGNORECASE)
    if generic or not re.search(r"[A-Za-z]", stem):
        base = album_title.strip() or "Gallery photo"
        return f"{base} — Photo {position}" if position else base
    words = re.sub(r"[-_]+", " ", stem).strip()
    words = re.sub(r"\s+", " ", words)
    return words[:1].upper() + words[1:220]


def validate_image_upload(upload, max_source_mb=4):
    if upload.size > max_source_mb * 1024 * 1024:
        raise ImageProcessingError(
            f"The image must be {max_source_mb} MB or smaller before processing. "
            "Keep this page open and choose the image again so the browser can optimize it."
        )
    head = upload.read(16)
    upload.seek(0)
    suffix = Path(upload.name).suffix.lower()
    detected = None
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        detected = "image/png"
    elif head.startswith(b"\xff\xd8\xff"):
        detected = "image/jpeg"
    elif head.startswith(b"RIFF") and head[8:12] == b"WEBP":
        detected = "image/webp"
    if suffix not in {".jpg", ".jpeg", ".png", ".webp"} or not detected:
        raise ImageProcessingError("Upload a valid JPG, PNG, or WebP image.")
    upload.detected_content_type = detected
    return upload


def optimize_image_upload(upload, max_bytes=MAX_IMAGE_BYTES, max_edge=MAX_IMAGE_EDGE):
    """Normalize orientation and return a progressive JPEG below the byte ceiling."""
    upload.seek(0)
    try:
        image = Image.open(upload)
        image.load()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ImageProcessingError("Upload a valid JPG, PNG, or WebP image.") from exc
    image = ImageOps.exif_transpose(image)
    if image.mode in {"RGBA", "LA"} or (image.mode == "P" and "transparency" in image.info):
        rgba = image.convert("RGBA")
        background = Image.new("RGB", rgba.size, "white")
        background.paste(rgba, mask=rgba.getchannel("A"))
        image = background
    else:
        image = image.convert("RGB")
    image.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
    quality = 88
    while True:
        output = BytesIO()
        image.save(output, format="JPEG", quality=quality, optimize=True, progressive=True)
        data = output.getvalue()
        if len(data) <= max_bytes:
            break
        if quality > 52:
            quality -= 7
            continue
        width, height = image.size
        if max(width, height) <= 900:
            raise ImageProcessingError("This image could not be reduced below 1 MB.")
        image = image.resize((max(1, int(width * .82)), max(1, int(height * .82))), Image.Resampling.LANCZOS)
        quality = 78
    filename = f"{Path(upload.name).stem[:165] or 'portal-image'}.jpg"
    return data, filename, "image/jpeg"
