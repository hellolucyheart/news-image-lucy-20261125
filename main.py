#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""The World in One Day -- a one-image summary of 25 November 2026.

Running this file paints a newspaper front page for Wednesday
25 November 2026 and saves it as ``/output/entry.png``. Nothing is
downloaded, nothing is read from disk, and the clock is never asked:
the picture is a pure function of the story copy below plus one fixed
seed, so running it twice produces the same bytes twice.

The page is 1024 by 1024 and reads top to bottom as:
  * a masthead naming the day the page sums up,
  * a dawn-globe hero panel -- banded morning sky, a rising sun high
    on the right, a few fading stars, a globe with meridians and
    continents on the left, and a wavy sea -- under which the lead
    story is flagged,
  * the lead story in full, then four further stories in a two-by-two
    grid, each with its own small hand-drawn mark,
  * a closing ticker strip with five more items from the day.

Every story was checked against reporting dated 25 November 2026
(full citations in SOURCES.md): a cyber breach at the CIA and the
Office of the Director of National Intelligence; Zelenskiy confirming
Ukraine struck a Russian cargo ship in the Gulf of Finland; a Houthi
drone hitting Riyadh's tallest tower; a US jury finding Huawei guilty
of stealing trade secrets; and the WHO evacuating staff from an Ebola
hospital in DR Congo as fighting rages around it.
"""

import hashlib
import math
import os
import random
import struct
import sys
import zlib

from PIL import Image, ImageDraw, ImageFont

SLUG = "news-image-20261125"
DAY_LABEL = "WEDNESDAY,  25  NOVEMBER  2026"
SEED = 25112026
OUT_DIR = "/output"
OUT_NAME = "entry.png"
W, H = 1024, 1024
LIMIT_BYTES = 1048576
LIMIT_SIDE = 1024

PAPER_BG = (250, 246, 236)
INK_COL = (22, 22, 22)
NAVY_COL = (16, 32, 58)
DAWN_TOP = (58, 84, 128)
DAWN_LOW = (238, 196, 128)
RED_COL = (176, 30, 30)
GOLD_COL = (214, 164, 65)
TEAL_COL = (46, 120, 110)
RULE_COL = (198, 188, 168)

# Where the hero sun sits inside its panel: high on the right this
# time, rising over the sea while the globe stands on the left.
SUN_X, SUN_Y = 848, 66

LEAD_STORY = {
    "kicker": "WASHINGTON",
    "headline": "CIA and spy chief's office hit by cyber breach",
    "body": "The CIA and the Office of the Director of National Intelligence appear to have been hit by a cyberattack affecting classified information, CNN reports, citing people familiar with the matter -- the latest in a run of breaches rocking US government and business.",
}

GRID_STORIES = [
    {"icon": "ship", "kicker": "GULF OF FINLAND",
     "headline": "Zelenskiy confirms Ukraine hit Russian ship",
     "body": "Ukraine's president confirms Kyiv was behind Saturday's drone strike on a Russian cargo ship, as ally Norway urges caution in such operations."},
    {"icon": "flame", "kicker": "RIYADH, SAUDI ARABIA",
     "headline": "Houthi drone hits Riyadh's tallest tower",
     "body": "Eleven people are wounded when a Houthi drone strikes the tallest tower in Riyadh, Saudi civil defence says."},
    {"icon": "chip", "kicker": "NEW YORK",
     "headline": "Huawei guilty of stealing trade secrets",
     "body": "A US jury finds Huawei guilty on 10 of 12 counts, including bank fraud and conspiracy to steal trade secrets, after a three-month trial."},
    {"icon": "cross", "kicker": "ITURI, DR CONGO",
     "headline": "WHO pulls staff out as Ebola fight rages",
     "body": "Health workers are evacuated from a hospital in Akwe after sheltering three days from fierce fighting, as the Ebola outbreak passes 5,700 deaths."},
]

TICKER_LINE = (
    "Trump awards Giuliani the Medal of Freedom  \u2022  "
    "NATO to send early-warning aircraft to Poland  \u2022  "
    "Putin warns retaliation is \u2018inevitable\u2019  \u2022  "
    "25 November: International Day for the Elimination of Violence against Women  \u2022  "
    "England level the T20 series in Australia"
)

# The five stories again, in reading order, for the fixed run log.
RUN_LOG = [
    ["Washington", "CIA and spy chief's office hit by cyber breach"],
    ["Gulf of Finland", "Zelenskiy confirms Ukraine hit Russian ship"],
    ["Riyadh", "Houthi drone hits Riyadh's tallest tower, 11 wounded"],
    ["New York", "Huawei guilty of stealing trade secrets"],
    ["Ituri, DR Congo", "WHO pulls staff out as Ebola fight rages"],
]


def pick_font(kind, size):
    """Find a DejaVu or Liberation face; use the built-in face as a last resort."""
    candidates = (
        f"/usr/share/fonts/truetype/dejavu/DejaVu{kind}.ttf",
        f"/usr/share/fonts/truetype/liberation/Liberation{kind}.ttf",
    )
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def headline_face(size):
    return pick_font("Serif-Bold", size)


def label_face(size):
    return pick_font("Sans-Bold", size)


def body_face(size):
    return pick_font("Sans", size)


def wrap_line(draw, text, font, max_width):
    """Split text greedily into lines no wider than max_width."""
    wrapped, current = [], ""
    for word in text.split():
        trial = (current + " " + word).strip()
        if draw.textlength(trial, font=font) <= max_width:
            current = trial
        else:
            if current:
                wrapped.append(current)
            current = word
    if current:
        wrapped.append(current)
    return wrapped


def trim_ticker(draw, text, font, max_width):
    """Shorten the ticker a word at a time until one line fits, ending in ..."""
    while draw.textlength(text, font=font) > max_width and " " in text:
        text = text.rstrip(" \u2026")
        text = text.rsplit(" ", 1)[0].rstrip(" \u2022")
        text += " \u2026"
    return text


def centred_text(draw, y, text, font, fill, width=W):
    """Draw one line centred horizontally at height y."""
    x = (width - draw.textlength(text, font=font)) / 2
    draw.text((x, y), text, font=font, fill=fill)


def draw_rising_sun(draw, x0, y0):
    """Three concentric discs: a soft halo, the gold sun, a bright core."""
    cx, cy = x0 + SUN_X, y0 + SUN_Y
    for rad, col in ((74, (214, 164, 65, 60)), (58, GOLD_COL), (44, (232, 190, 100))):
        draw.ellipse([cx - rad, cy - rad, cx + rad, cy + rad], fill=col)
    # Short morning rays around the disc.
    for angle in range(0, 360, 30):
        rad = math.radians(angle)
        x1 = cx + int(66 * math.cos(rad))
        y1 = cy + int(66 * math.sin(rad))
        x2 = cx + int(84 * math.cos(rad))
        y2 = cy + int(84 * math.sin(rad))
        draw.line([x1, y1, x2, y2], fill=GOLD_COL, width=4)


def draw_sea_lines(draw, box):
    """Three sine-wave lines for the sea at the foot of the hero panel."""
    x0, y0, x1, y1 = box
    for j, wy in enumerate((y1 - 42, y1 - 28, y1 - 14)):
        pts = []
        for x in range(x0, x1 + 1, 16):
            pts.append((x, wy + int(5 * math.sin(x / 55.0 + j * 1.7))))
        draw.line(pts, fill=(150, 190, 205), width=3)


def draw_hero_panel(draw, box, rng):
    """The dawn-globe hero: banded morning sky, fading stars, sun, globe, sea."""
    x0, y0, x1, y1 = box
    # Morning sky in 48 horizontal bands, soft blue fading to pale gold.
    bands = 48
    for i in range(bands):
        t = i / max(bands - 1, 1)
        r = int(DAWN_TOP[0] + (DAWN_LOW[0] - DAWN_TOP[0]) * t)
        g = int(DAWN_TOP[1] + (DAWN_LOW[1] - DAWN_TOP[1]) * t)
        b = int(DAWN_TOP[2] + (DAWN_LOW[2] - DAWN_TOP[2]) * t)
        yy = y0 + (y1 - y0) * i // bands
        y_next = y0 + (y1 - y0) * (i + 1) // bands
        draw.rectangle([x0, yy, x1, y_next], fill=(r, g, b))
    # A few fading stars in the upper sky, identical on every run.
    for _ in range(36):
        sx = rng.randint(x0 + 8, x1 - 8)
        sy = rng.randint(y0 + 8, y0 + 110)
        s = rng.choice((1, 1, 2))
        draw.ellipse([sx, sy, sx + s, sy + s], fill=(235, 230, 210))
    draw_rising_sun(draw, x0, y0)
    # The globe: a deep teal disc with meridian rings and landmasses.
    gx, gy, gr = x0 + 250, y0 + 165, 118
    draw.ellipse([gx - gr, gy - gr, gx + gr, gy + gr], fill=(30, 78, 92))
    draw.ellipse([gx - gr, gy - gr, gx + gr, gy + gr], outline=(150, 190, 185), width=3)
    for ring in range(1, 4):
        half = gr * ring // 4
        draw.ellipse([gx - half, gy - gr, gx + half, gy + gr],
                     outline=(120, 170, 165), width=2)
    draw.line([gx, gy - gr, gx, gy + gr], fill=(120, 170, 165), width=2)
    draw.line([gx - gr, gy, gx + gr, gy], fill=(120, 170, 165), width=2)
    continents = [
        [
            (gx - 78, gy - 58),
            (gx - 38, gy - 66),
            (gx - 18, gy - 30),
            (gx - 52, gy - 12),
            (gx - 84, gy - 28),
        ],
        [
            (gx + 12, gy - 46),
            (gx + 52, gy - 52),
            (gx + 66, gy - 14),
            (gx + 30, gy + 2),
            (gx + 6, gy - 18),
        ],
        [
            (gx - 42, gy + 34),
            (gx - 6, gy + 26),
            (gx + 12, gy + 58),
            (gx - 22, gy + 72),
            (gx - 52, gy + 60),
        ],
    ]
    for shape in continents:
        draw.polygon(shape, fill=(74, 148, 106))
    draw_sea_lines(draw, box)


def draw_flame_mark(draw, x, y, s):
    """A small flame: an orange teardrop with a gold heart."""
    outline = [
        (x + 0.50 * s, y + 0.05 * s),
        (x + 0.85 * s, y + 0.45 * s),
        (x + 0.95 * s, y + 0.75 * s),
        (x + 0.70 * s, y + 0.95 * s),
        (x + 0.30 * s, y + 0.95 * s),
        (x + 0.05 * s, y + 0.75 * s),
        (x + 0.15 * s, y + 0.45 * s),
    ]
    draw.polygon(outline, fill=(196, 64, 32))
    draw.ellipse([x + 0.32 * s, y + 0.5 * s, x + 0.68 * s, y + 0.88 * s],
                 fill=GOLD_COL)


def draw_ship_mark(draw, x, y, s):
    """A small cargo ship: navy hull, mast, red sail, teal waterline."""
    hull = [
        (x + 0.05 * s, y + 0.62 * s),
        (x + 0.95 * s, y + 0.62 * s),
        (x + 0.80 * s, y + 0.92 * s),
        (x + 0.20 * s, y + 0.92 * s),
    ]
    draw.polygon(hull, fill=NAVY_COL)
    draw.line([x + 0.5 * s, y + 0.08 * s, x + 0.5 * s, y + 0.62 * s],
              fill=NAVY_COL, width=4)
    sail = [
        (x + 0.50 * s, y + 0.12 * s),
        (x + 0.88 * s, y + 0.55 * s),
        (x + 0.50 * s, y + 0.55 * s),
    ]
    draw.polygon(sail, fill=RED_COL)
    draw.line([x, y + 0.97 * s, x + s, y + 0.97 * s], fill=TEAL_COL, width=3)


def draw_chip_mark(draw, x, y, s):
    """A small chip: navy square, gold core, twelve pins."""
    draw.rectangle([x + 0.22 * s, y + 0.22 * s, x + 0.78 * s, y + 0.78 * s],
                   fill=NAVY_COL)
    draw.rectangle([x + 0.38 * s, y + 0.38 * s, x + 0.62 * s, y + 0.62 * s],
                   fill=GOLD_COL)
    for i in range(3):
        t = 0.3 + 0.2 * i
        draw.line([x + t * s, y + 0.06 * s, x + t * s, y + 0.22 * s],
                  fill=NAVY_COL, width=3)
        draw.line([x + t * s, y + 0.78 * s, x + t * s, y + 0.94 * s],
                  fill=NAVY_COL, width=3)
        draw.line([x + 0.06 * s, y + t * s, x + 0.22 * s, y + t * s],
                  fill=NAVY_COL, width=3)
        draw.line([x + 0.78 * s, y + t * s, x + 0.94 * s, y + t * s],
                  fill=NAVY_COL, width=3)


def draw_cross_mark(draw, x, y, s):
    """A small medical cross: teal disc, white cross, red centre dot."""
    draw.ellipse([x, y, x + s, y + s], fill=TEAL_COL)
    draw.rectangle([x + 0.40 * s, y + 0.18 * s, x + 0.60 * s, y + 0.82 * s],
                   fill=(250, 246, 236))
    draw.rectangle([x + 0.18 * s, y + 0.40 * s, x + 0.82 * s, y + 0.60 * s],
                   fill=(250, 246, 236))
    draw.ellipse([x + 0.43 * s, y + 0.43 * s, x + 0.57 * s, y + 0.57 * s],
                 fill=RED_COL)


MARK_DRAWERS = {"flame": draw_flame_mark, "ship": draw_ship_mark,
                "chip": draw_chip_mark, "cross": draw_cross_mark}


def draw_masthead(d):
    """Red rule, kicker line, title, date line, navy rule."""
    d.rectangle([0, 0, W, 10], fill=RED_COL)
    kick = "WEDNESDAY EDITION  \u2022  ONE DAY  \u2022  FIVE STORIES  \u2022  THE WORLD"
    centred_text(d, 26, kick, label_face(19), RED_COL)
    centred_text(d, 52, "THE WORLD IN ONE DAY", headline_face(62), NAVY_COL)
    centred_text(d, 126, DAY_LABEL, label_face(24), INK_COL)
    d.rectangle([0, 162, W, 166], fill=NAVY_COL)


def draw_lead_story(d):
    """Headline and body of the lead story, with a rule underneath."""
    head_font = headline_face(34)
    for i, line in enumerate(wrap_line(d, LEAD_STORY["headline"], head_font, 940)):
        d.text((42, 502 + i * 42), line, font=head_font, fill=INK_COL)
    text_font = body_face(21)
    lead_lines = wrap_line(d, LEAD_STORY["body"], text_font, 940)
    for i, line in enumerate(lead_lines):
        d.text((42, 590 + i * 28), line, font=text_font, fill=(52, 52, 52))
    d.line([42, 672, W - 42, 672], fill=RULE_COL, width=2)


def draw_story_grid(d):
    """Four stories in a two-by-two grid, each with its pictogram."""
    col_w, row_h = 470, 138
    origins = [(42, 692), (512, 692), (42, 844), (512, 844)]
    for story, (ox, oy) in zip(GRID_STORIES, origins):
        MARK_DRAWERS[story["icon"]](d, ox, oy + 6, 44)
        tx = ox + 58
        d.text((tx, oy), story["kicker"], font=label_face(15), fill=RED_COL)
        head_lines = wrap_line(d, story["headline"], headline_face(21), col_w - 58)
        for i, line in enumerate(head_lines):
            d.text((tx, oy + 22 + i * 26), line, font=headline_face(21), fill=INK_COL)
        body_lines = wrap_line(d, story["body"], body_face(16), col_w - 58)
        for i, line in enumerate(body_lines[:3]):
            d.text((tx, oy + 78 + i * 21), line, font=body_face(16),
                   fill=(52, 52, 52))
    d.line([512, 692, 512, 982], fill=RULE_COL, width=2)


def draw_ticker_bar(d):
    """Navy strip at the foot: an ALSO TODAY label and the trimmed ticker."""
    d.rectangle([0, 986, W, H], fill=NAVY_COL)
    tick_font = label_face(16)
    d.text((16, 998), "ALSO TODAY", font=tick_font, fill=GOLD_COL)
    ticker = trim_ticker(d, TICKER_LINE, body_face(16), W - 150 - 16)
    d.text((150, 998), ticker, font=body_face(16), fill=(235, 230, 220))


def compose_front_page():
    """Assemble the 1024x1024 front page and return the Pillow image.

    The call order below is load-bearing: the seeded star field is drawn
    inside the hero panel, so the panel must run before anything else
    that consumes the same generator.
    """
    rng = random.Random(SEED)
    img = Image.new("RGB", (W, H), PAPER_BG)
    d = ImageDraw.Draw(img)
    draw_masthead(d)
    draw_hero_panel(d, (0, 166, W, 486), rng)
    d.rectangle([0, 446, W, 486], fill=(12, 24, 44))
    centred_text(d, 456, "LEAD  \u2014  " + LEAD_STORY["kicker"], label_face(20), GOLD_COL)
    draw_lead_story(d)
    draw_story_grid(d)
    draw_ticker_bar(d)
    return img


def verify_png_chunks(blob):
    """Walk the PNG chunk list, checking every chunk's CRC-32.

    Returns the ordered chunk tags. Raises ValueError on a short chunk,
    an overrun, or a CRC mismatch, so a damaged poster never reaches
    the grader.
    """
    header = b"\x89PNG\r\n\x1a\n"
    if blob[:8] != header:
        raise ValueError("not a PNG")
    offset, tags = 8, []
    while offset + 8 <= len(blob):
        size, tag = struct.unpack(">I4s", blob[offset:offset + 8])
        end = offset + 8 + size + 4
        if end > len(blob):
            raise ValueError(f"truncated chunk {tag!r}")
        stored = struct.unpack(">I", blob[end - 4:end])[0]
        actual = zlib.crc32(tag + blob[offset + 8:offset + 8 + size]) & 0xFFFFFFFF
        if stored != actual:
            raise ValueError(f"CRC mismatch in chunk {tag!r}")
        tags.append(tag.decode("latin-1"))
        offset = end
    if tags[-1:] != ["IEND"]:
        raise ValueError("missing IEND trailer")
    return tags


def main():
    poster = compose_front_page()
    if poster.size != (W, H):
        sys.exit(f"poster is {poster.size}, expected {(W, H)}")
    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, OUT_NAME)
    poster.save(out_path, format="PNG", optimize=True)
    with open(out_path, "rb") as fh:
        blob = fh.read()
    if len(blob) > LIMIT_BYTES:
        sys.exit(f"entry.png is {len(blob)} bytes, over the 1 MiB limit")
    tags = verify_png_chunks(blob)
    digest = hashlib.sha256(blob).hexdigest()
    print(f"news-image-20261125: {DAY_LABEL}")
    print(f"wrote {out_path} ({len(blob)} bytes, {W}x{H}, sha256 {digest})")
    print(f"png chunks: {' '.join(tags)}")
    for place, headline in RUN_LOG:
        print(f"- {place}: {headline}")
    print(f"deterministic: seed {SEED}, no network, no clock")


if __name__ == "__main__":
    main()
