"""Deterministic processing for public gallery uploads."""

from io import BytesIO
from pathlib import Path
import re

from PIL import Image, ImageOps, UnidentifiedImageError


MAX_GALLERY_BYTES = 950 * 1024
MAX_GALLERY_EDGE = 2400


class GalleryImageError(ValueError):
    pass


def automatic_caption(filename, album_title="", position=None):
    """Turn a useful filename into a caption, with an album-based camera-name fallback."""
    stem = Path(filename).stem
    generic = re.fullmatch(r"(?:img|dsc|dscn|pxl|photo|image)[-_ ]?\d+", stem, re.IGNORECASE)
    if generic or not re.search(r"[A-Za-z]", stem):
        base = album_title.strip() or "Gallery photo"
        return f"{base} — Photo {position}" if position else base
    words = re.sub(r"[-_]+", " ", stem).strip()
    words = re.sub(r"\s+", " ", words)
    return words[:1].upper() + words[1:220]


def optimize_gallery_image(upload):
    """Normalize orientation and encode a web-sized JPEG below the gallery byte ceiling."""
    try:
        image = Image.open(upload)
        image.load()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise GalleryImageError("Upload a valid JPG, PNG, or WebP image.") from exc

    image = ImageOps.exif_transpose(image)
    if image.mode in {"RGBA", "LA"} or (image.mode == "P" and "transparency" in image.info):
        rgba = image.convert("RGBA")
        background = Image.new("RGB", rgba.size, "white")
        background.paste(rgba, mask=rgba.getchannel("A"))
        image = background
    else:
        image = image.convert("RGB")
    image.thumbnail((MAX_GALLERY_EDGE, MAX_GALLERY_EDGE), Image.Resampling.LANCZOS)

    quality = 88
    while True:
        output = BytesIO()
        image.save(output, format="JPEG", quality=quality, optimize=True, progressive=True)
        data = output.getvalue()
        if len(data) <= MAX_GALLERY_BYTES:
            break
        if quality > 52:
            quality -= 7
            continue
        width, height = image.size
        if max(width, height) <= 900:
            raise GalleryImageError("This image could not be reduced below 1 MB.")
        image = image.resize((max(1, int(width * .82)), max(1, int(height * .82))), Image.Resampling.LANCZOS)
        quality = 78

    filename = f"{Path(upload.name).stem[:165] or 'gallery-photo'}.jpg"
    return data, filename, "image/jpeg"
