"""Build annotated before/after GIFs from the saved, unaltered browser captures.

Requires Pillow. Source screenshots stay untouched; generated files go in visuals/.
Run: python make-visuals.py
"""

from pathlib import Path
from math import atan2, cos, sin, pi

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "visuals"
OUT.mkdir(exist_ok=True)
SCALE = 0.75
W, H, BAR = 960, 600, 72
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
TITLE_FONT = ImageFont.truetype(BOLD, 26)
SUB_FONT = ImageFont.truetype(FONT, 15)
LABEL_FONT = ImageFont.truetype(BOLD, 16)
WHITE = (245, 250, 255)
MUTED = (179, 198, 213)
AMBER = (255, 187, 48)
CYAN = (81, 211, 255)


def xy(point):
    return round(point[0] * SCALE), round(point[1] * SCALE) + BAR


def arrow(draw, start, end, color):
    a, b = xy(start), xy(end)
    draw.line([a, b], fill=(4, 11, 20), width=12, joint="curve")
    draw.line([a, b], fill=color, width=6, joint="curve")
    angle = atan2(b[1] - a[1], b[0] - a[0])
    length, spread = 20, pi / 7
    p1 = (b[0] - length * cos(angle - spread), b[1] - length * sin(angle - spread))
    p2 = (b[0] - length * cos(angle + spread), b[1] - length * sin(angle + spread))
    draw.polygon([b, p1, p2], fill=color, outline=(4, 11, 20), width=2)
    r = 14
    draw.ellipse((b[0] - r, b[1] - r, b[0] + r, b[1] + r), outline=color, width=4)


def tag(draw, text, at, color):
    x, y = xy(at)
    box = draw.textbbox((0, 0), text, font=LABEL_FONT)
    tw, th = box[2] - box[0], box[3] - box[1]
    x = min(max(6, x), W - tw - 24)
    y = min(max(BAR + 6, y), BAR + H - th - 22)
    draw.rounded_rectangle((x, y, x + tw + 20, y + th + 16), radius=7, fill=(10, 24, 37), outline=color, width=2)
    draw.text((x + 10, y + 5), text, font=LABEL_FONT, fill=WHITE)


def frame(src, phase, title, subtitle, callouts):
    source = Image.open(ROOT / src).convert("RGB")
    if source.size != (1280, 800):
        raise ValueError(f"Unexpected screenshot size: {src}: {source.size}")
    page = Image.new("RGB", (W, BAR + H), (13, 26, 40))
    page.paste(source.resize((W, H), Image.Resampling.LANCZOS), (0, BAR))
    d = ImageDraw.Draw(page)
    color = AMBER if phase == "BEFORE" else CYAN
    d.rectangle((0, 0, 9, BAR), fill=color)
    d.text((25, 10), f"{phase}  ·  {title}", font=TITLE_FONT, fill=WHITE)
    d.text((26, 45), subtitle, font=SUB_FONT, fill=MUTED)
    for label, label_at, start, end in callouts:
        arrow(d, start, end, color)
        tag(d, label, label_at, color)
    return page


COMPARISONS = [
    (
        "store",
        ("frame-store-before.png", "Store opened empty", "A search was required before any game appeared.", [
            ("No games here", (865, 560), (1080, 560), (835, 610)),
        ]),
        ("frame-store-pass3.png", "Browse games immediately", "Starting titles, filters, prices and actions are visible.", [
            ("Catalog filters", (650, 210), (790, 280), (590, 260)),
            ("Game rows", (840, 470), (990, 530), (690, 495)),
        ]),
    ),
    (
        "search",
        ("frame-search-before.png", "Ten large cards", "Only ten suggestions were shown; the broader count was hidden.", [
            ("10 of 10", (295, 250), (440, 250), (225, 282)),
            ("Large cards", (810, 515), (970, 590), (610, 560)),
        ]),
        ("frame-search-pass3.png", "Full results and compact rows", "Count, paging, catalog filters and metadata support scanning.", [
            ("325 results", (315, 115), (495, 125), (185, 152)),
            ("Catalog filters", (880, 205), (1040, 265), (570, 263)),
            ("Five rows", (825, 525), (1000, 620), (640, 525)),
        ]),
    ),
    (
        "installed",
        ("frame-installed-before.png", "Hidden game controls", "The cover had no visible name or Play action until interaction.", [
            ("Unlabelled cover", (310, 490), (460, 520), (120, 510)),
        ]),
        ("frame-installed-pass3.png", "Ready-to-play library", "Name and Play stay visible; Steam search is available here.", [
            ("Search Steam", (725, 260), (880, 295), (1050, 205)),
            ("Name + Play", (320, 625), (470, 640), (125, 650)),
        ]),
    ),
    (
        "details",
        ("frame-detail-after.png", "Early detail view", "The first pass had static art and facts below it.", [
            ("Static header", (710, 160), (850, 210), (420, 190)),
            ("Basic facts", (760, 550), (900, 565), (260, 515)),
        ]),
        ("frame-detail-pass4.png", "Media-rich game details", "Playable trailer, clean gallery, reviews, tags and VR facts.", [
            ("Playable trailer", (720, 155), (865, 195), (435, 245)),
            ("Reviews + actions", (795, 370), (1000, 410), (830, 270)),
            ("Tags + media", (790, 580), (980, 600), (420, 540)),
        ]),
    ),
]


after_frames = []
for key, before, after in COMPARISONS:
    before_image = frame(before[0], "BEFORE", before[1], before[2], before[3])
    after_image = frame(after[0], "AFTER", after[1], after[2], after[3])
    frames = [before_image, after_image]
    frames[0].save(
        OUT / f"{key}-before-after.gif",
        save_all=True,
        append_images=frames[1:],
        duration=[1800, 2800],
        loop=0,
        optimize=True,
        disposal=2,
    )
    after_image.save(OUT / f"{key}-after-annotated.png", optimize=True)
    after_frames.append(after_image)

poster = Image.new("RGB", (W * 2 + 16, (H + BAR) * 2 + 16), (7, 17, 28))
for i, image in enumerate(after_frames):
    poster.paste(image, ((i % 2) * (W + 16), (i // 2) * (BAR + H + 16)))
poster.save(OUT / "changes-overview.png", optimize=True)
print(f"Wrote {len(COMPARISONS)} GIFs, annotated PNGs and overview to {OUT}")
