"""Flat-color icons are refused once one color covers 90% of the picture."""

import io
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from server.engine.distiller import Distiller
from server.engine.icon_quality import is_unusable_icon, strip_solid_icons


def _png(colors):
    width = len(colors[0])
    height = len(colors)
    image = Image.new("RGBA", (width, height))
    pixels = image.load()
    for y, row in enumerate(colors):
        for x, color in enumerate(row):
            pixels[x, y] = color
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def _solid(color, size=16):
    return _png([[color] * size for _ in range(size)])


class SolidIconTests(unittest.TestCase):
    def test_flat_purple_is_refused(self):
        self.assertTrue(is_unusable_icon(_solid((124, 58, 237, 255))))

    def test_near_purple_noise_still_counts_as_one_color(self):
        rows = []
        for y in range(16):
            row = []
            for x in range(16):
                row.append((124 + (x % 3) * 4, 58 + (y % 2) * 6, 237 - (x % 2) * 5, 255))
            rows.append(row)
        self.assertTrue(is_unusable_icon(_png(rows)))

    def test_eleven_percent_of_a_second_color_is_allowed(self):
        # 10 x 10, 11 pixels of a second color → 89% of the rest.
        rows = []
        second = 0
        for y in range(10):
            row = []
            for x in range(10):
                if second < 11:
                    row.append((255, 255, 255, 255))
                    second += 1
                else:
                    row.append((124, 58, 237, 255))
            rows.append(row)
        self.assertFalse(is_unusable_icon(_png(rows)))

    def test_exactly_ninety_percent_is_refused(self):
        rows = []
        other = 0
        for y in range(10):
            row = []
            for x in range(10):
                if other < 10:
                    row.append((255, 255, 255, 255))
                    other += 1
                else:
                    row.append((20, 20, 20, 255))
            rows.append(row)
        self.assertTrue(is_unusable_icon(_png(rows)))

    def test_clear_canvas_around_a_real_picture_is_judged_on_the_picture(self):
        image = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
        pixels = image.load()
        for y in range(8):
            for x in range(8):
                pixels[x, y] = ((x * 30) % 256, (y * 20) % 256, 40 + x * y, 255)
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        self.assertFalse(is_unusable_icon(buf.getvalue()))

    def test_custom_solid_upload_is_dropped_and_flagged(self):
        distiller = Distiller()
        raw = _solid((124, 58, 237, 255))
        data_url = "data:image/png;base64," + __import__("base64").b64encode(raw).decode()
        recipe = {"url": "https://example.com", "color": "#7c3aed", "_custom_icon_data_url": data_url}
        self.assertIsNone(distiller._fetch_icon(recipe))
        self.assertEqual(recipe.get("_icon_rejected"), "solid")

    def test_strip_removes_only_flat_icons(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            flat = root / "flatapp1"
            real = root / "realapp1"
            flat.mkdir()
            real.mkdir()
            (flat / "icon.png").write_bytes(_solid((124, 58, 237, 255)))
            (flat / "page.html").write_text("old", encoding="utf-8")
            (real / "icon.png").write_bytes(_png([
                [(255, 0, 0, 255), (0, 255, 0, 255)],
                [(0, 0, 255, 255), (255, 255, 0, 255)],
            ]))
            self.assertEqual(strip_solid_icons(root), 1)
            self.assertFalse((flat / "icon.png").exists())
            self.assertFalse((flat / "page.html").exists())
            self.assertTrue((real / "icon.png").exists())
