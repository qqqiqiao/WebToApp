"""Reject icons that are essentially one flat color.

The market was filling up with the same purple square: that file is the
solid placeholder painted when a site has no favicon. A real icon has more
than one color. An icon is unusable when 90% or more of its visible pixels
sit close to a single color. Fully transparent pixels are ignored, so a
small picture centered on a clear canvas is judged by the picture itself.
"""

import io
from pathlib import Path

from PIL import Image, UnidentifiedImageError

SOLID_ICON_RATIO = 0.90
# How far a pixel may drift from the average and still count as the same color.
_COLOR_TOLERANCE = 24
_MAX_SAMPLES = 4096


def dominant_opaque_ratio(data: bytes) -> float:
    """Share of visible pixels that are close to the image's average color.

    Returns 1.0 for an empty or fully transparent image. Raises if the bytes
    are not a readable raster image.
    """
    with Image.open(io.BytesIO(data)) as image:
        image = image.convert("RGBA")
        width, height = image.size
        if width <= 0 or height <= 0:
            return 1.0
        step = max(1, int((width * height / _MAX_SAMPLES) ** 0.5))
        pixels = image.load()
        samples = []
        for y in range(0, height, step):
            for x in range(0, width, step):
                red, green, blue, alpha = pixels[x, y]
                if alpha < 128:
                    continue
                samples.append((red, green, blue))
    if not samples:
        return 1.0
    count = len(samples)
    mean_red = sum(pixel[0] for pixel in samples) / count
    mean_green = sum(pixel[1] for pixel in samples) / count
    mean_blue = sum(pixel[2] for pixel in samples) / count
    close = 0
    for red, green, blue in samples:
        if max(abs(red - mean_red), abs(green - mean_green), abs(blue - mean_blue)) <= _COLOR_TOLERANCE:
            close += 1
    return close / count


def is_unusable_icon(data: bytes, limit: float = SOLID_ICON_RATIO) -> bool:
    """True when the image is blank or at least `limit` one color."""
    if not data:
        return False
    try:
        ratio = dominant_opaque_ratio(data)
    except (UnidentifiedImageError, OSError, ValueError):
        return False
    return ratio + 1e-9 >= limit


def strip_solid_icons(apps_dir: Path) -> int:
    """Delete public icon files that are a flat color. Returns how many went."""
    root = Path(apps_dir)
    if not root.is_dir():
        return 0
    removed = 0
    for icon_path in root.glob("*/icon.png"):
        if icon_path.parent.name.startswith("_"):
            continue
        try:
            data = icon_path.read_bytes()
        except OSError:
            continue
        if not is_unusable_icon(data):
            continue
        try:
            icon_path.unlink()
        except OSError:
            continue
        # The cached download page still points at this file. Drop it so the
        # next visit renders without the flat square.
        page_path = icon_path.parent / "page.html"
        try:
            if page_path.is_file():
                page_path.unlink()
        except OSError:
            pass
        removed += 1
    return removed
