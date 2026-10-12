"""Certificate rendering. The official template image is the background; only the participant's
name and department are overlaid on its two blank lines. One layout function drives both the PDF
and the JPEG preview so they always match."""
import hashlib
import os
import re
import secrets
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from . import config

TPL_W, TPL_H = 6250, 4419          # pixel grid of the original supplied template (measured)
PAGE_W = 841.89                    # A4 landscape in points
SCALE = PAGE_W / TPL_W
PAGE_H = TPL_H * SCALE
TEXT_COLOR = (16, 18, 62)          # Midnight Navy #10123E
FONT_PATH = str(config.ASSETS_DIR / "fonts" / "Poppins-Bold.ttf")
TEMPLATE_PATH = str(config.ASSETS_DIR / "certificate_template.jpg")

# Blank lines printed on the template (template pixels). base = text baseline just above the line.
FIELDS = {
    "name": {"x0": 1925, "x1": 5825, "base": 2186},
    "department": {"x0": 770, "x1": 5825, "base": 2409},
}
PAD = 25
MAX_SIZE, MIN_SIZE = 92, 40

try:
    pdfmetrics.registerFont(TTFont("Poppins-Bold", FONT_PATH))
except Exception:  # pragma: no cover
    pass


@lru_cache(maxsize=64)
def _font(size):
    return ImageFont.truetype(FONT_PATH, size)


def layout(field, text):
    """-> (text, size_px, x_px, baseline_px). Shrinks to fit; ellipsis only below the minimum size."""
    f = FIELDS[field]
    avail = f["x1"] - f["x0"] - 2 * PAD
    for size in range(MAX_SIZE, MIN_SIZE - 1, -1):
        if _font(size).getlength(text) <= avail:
            return text, size, f["x0"] + PAD, f["base"]
    size = MIN_SIZE
    while text and _font(size).getlength(text + "…") > avail:
        text = text[:-1]
    return text.rstrip() + "…", size, f["x0"] + PAD, f["base"]


def data_hash(name, department):
    return hashlib.sha256(f"{name}\x1f{department}".encode()).hexdigest()[:32]


def new_certificate_id():
    return "TS26-" + secrets.token_hex(4).upper()


def safe_filename(name, suffix=""):
    base = re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_") or "Participant"
    return f"TechSphere_{base[:60]}{suffix}.pdf"


def _atomic(path, writer):
    tmp = f"{path}.tmp.{os.getpid()}"
    writer(tmp)
    os.replace(tmp, path)


def render_pdf(path, name, department, certificate_id):
    def write(tmp):
        c = canvas.Canvas(tmp, pagesize=(PAGE_W, PAGE_H))
        c.setTitle(f"Certificate of Participation - {name}")
        c.setAuthor(config.EVENT["college"])
        c.setSubject(f"TECHSPHERE-2K26 (Poster Presentation) | Certificate ID {certificate_id}")
        c.drawImage(ImageReader(TEMPLATE_PATH), 0, 0, PAGE_W, PAGE_H)
        c.setFillColorRGB(*(v / 255 for v in TEXT_COLOR))
        for field, text in (("name", name), ("department", department)):
            t, size, x, base = layout(field, text)
            c.setFont("Poppins-Bold", size * SCALE)
            c.drawString(x * SCALE, PAGE_H - base * SCALE, t)
        c.showPage()
        c.save()
    _atomic(str(path), write)


def render_preview(path, name, department, width=1800):
    k = width / TPL_W
    im = Image.open(TEMPLATE_PATH).convert("RGB").resize((width, round(TPL_H * k)), Image.LANCZOS)
    d = ImageDraw.Draw(im)
    for field, text in (("name", name), ("department", department)):
        t, size, x, base = layout(field, text)
        d.text((x * k, base * k), t, font=ImageFont.truetype(FONT_PATH, max(1, round(size * k))),
               fill=TEXT_COLOR, anchor="ls")
    _atomic(str(path), lambda tmp: im.save(tmp, format="JPEG", quality=88))
