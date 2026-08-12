"""Build the site's icon set from the University of Bayreuth mark.

    python tools/build_icons.py

The outputs are **committed**, like `web/static/geo/countries.json` and for the
same reason: they are assets rather than pipeline artefacts, and generating them
from a script makes their provenance a command somebody else can run instead of
a memory of which image editor was open that afternoon.

**What the mark is.** The university's logo is a square device followed by the
words UNIVERSITÄT BAYREUTH. Only the square is used here — a wordmark is
illegible at 32 px and says nothing a favicon has room to say. The square is a
black frame, a black rule tracing the top-left corner inward, and a green band
running from the bottom-left to the top-right.

**Why the geometry is written out below rather than parsed from the logo file.**
The official artwork (`UBT-logo.svg`, an Illustrator export) is not in this
repository and is not ours to redistribute. Its first three elements are the
square, and they are pure axis-aligned geometry plus one polygon: fifteen
numbers, reproduced verbatim in `FRAME`, `RULE` and `BAND`. Copying them makes
this tool runnable from a checkout alone, and `web/static/favicon.svg` — which
this tool writes — becomes the vector master the rest of the set is cut from.

**Why not a rasteriser.** Every segment of the mark is either axis-aligned or a
filled polygon, so the shapes are exact rectangles and one polygon; there is no
curve to approximate and no font to shape. Drawing them directly at 8x and
downsampling gives the same result an SVG renderer would, without adding
cairosvg or a headless browser to a project that needs neither. Pillow is
already a transitive dependency of the pipeline.

**Stroke joins.** The rule turns two right angles and the source strokes it with
a miter join, which at a right angle is exactly what you get by extending each
segment by half the stroke width at the joined end only. `RULE` therefore names
which ends are joins; the free ends keep SVG's default butt cap.
"""

from __future__ import annotations

import sys
from itertools import pairwise
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from lib import console
from lib.paths import ROOT, rel

STATIC = ROOT / "web" / "static"

#: The mark's own coordinate system, and the source file's. The frame's stroke
#: is centred on 0.872 and is 1.7434 wide, so it starts at 0.0003 and ends at
#: 164.9177 — the square is 164.918 units on a side and bleeds to every edge.
SIDE = 164.918

BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
#: The university's green, taken from the artwork. Not a token from the site's
#: palette and deliberately not reconciled with one: an institutional mark is
#: quoted, not restyled.
GREEN = (0, 157, 109)  # #009D6D

STROKE = 1.7434
HALF = STROKE / 2

#: The outer square, as the centre line of its stroke.
FRAME = (0.872, 0.872, 164.046, 164.046)

#: The inner rule: an open polyline, as its vertices. Its two interior vertices
#: are the joins; the first and last points are free ends.
RULE = (
    (8.576, 157.345),
    (8.576, 8.811),
    (57.988, 8.811),
    (57.988, 112.275),
)

#: The green band. A closed polygon, drawn over the rule and under the frame.
BAND = (
    (7.7, 157.345),
    (81.817, 157.345),
    (155.937, 83.225),
    (155.937, 46.33),
    (119.3, 46.33),
)

#: Drawn at this multiple of the target size and reduced with a Lanczos filter.
#: The mark's thinnest feature is the 1.7434-unit stroke, which at 32 px is a
#: third of a pixel; 8x gives that edge enough samples to land as grey rather
#: than as a dropped row.
SUPERSAMPLE = 8

#: A maskable icon may be cropped to any shape inside the icon's bounds, and the
#: guaranteed-visible region is the circle covering the middle 80%. The largest
#: square inside that circle has a side of 0.8 / sqrt(2) of the icon — the mark
#: is square, so this is the fraction it may occupy and no more.
MASKABLE_SCALE = 0.8 / 2**0.5

#: iOS does not crop an apple-touch-icon, it rounds its corners by roughly a
#: fifth of the width. The frame is the outermost feature of the mark, so it is
#: inset enough that the rounding cannot bite into it.
APPLE_SCALE = 0.82


def draw_mark(draw: ImageDraw.ImageDraw, origin: float, side: float) -> None:
    """Paint the mark into a `side`-wide box whose top-left corner is `origin`.

    Drawn in the source file's order — rule, then band, then frame — because the
    band covers the lower half of the rule's second upright and the frame is
    drawn over both. Reordering these would not be a different rendering of the
    same mark; it would be a different mark.
    """
    k = side / SIDE

    def at(*values: float) -> list[float]:
        return [origin + value * k for value in values]

    for index, ((x1, y1), (x2, y2)) in enumerate(pairwise(RULE)):
        # Half the stroke to either side of the centre line, plus the miter
        # overhang at whichever ends of this segment are interior vertices.
        start = HALF if index > 0 else 0.0
        end = HALF if index + 2 < len(RULE) else 0.0
        lo_x, hi_x = min(x1, x2), max(x1, x2)
        lo_y, hi_y = min(y1, y2), max(y1, y2)
        if x1 == x2:
            # Vertical: `start` belongs to whichever end the segment begins at.
            top, bottom = (start, end) if y1 < y2 else (end, start)
            box = (lo_x - HALF, lo_y - top, hi_x + HALF, hi_y + bottom)
        else:
            left, right = (start, end) if x1 < x2 else (end, start)
            box = (lo_x - left, lo_y - HALF, hi_x + right, hi_y + HALF)
        draw.rectangle(at(*box), fill=BLACK)

    draw.polygon([(origin + x * k, origin + y * k) for x, y in BAND], fill=GREEN)

    # The frame as four bars rather than an outlined rectangle: Pillow grows an
    # outline inward from the given box, which would put the stroke off its
    # centre line and leave the mark a stroke-width short of the edges.
    x1, y1, x2, y2 = FRAME
    for box in (
        (x1 - HALF, y1 - HALF, x2 + HALF, y1 + HALF),  # top
        (x1 - HALF, y2 - HALF, x2 + HALF, y2 + HALF),  # bottom
        (x1 - HALF, y1 - HALF, x1 + HALF, y2 + HALF),  # left
        (x2 - HALF, y1 - HALF, x2 + HALF, y2 + HALF),  # right
    ):
        draw.rectangle(at(*box), fill=BLACK)


def render(size: int, scale: float = 1.0) -> Image.Image:
    """One square PNG, `size` px, with the mark occupying `scale` of it.

    The ground is opaque white at every size. The mark is black and green line
    work drawn for paper, and on a transparent ground it would vanish into the
    dark theme, into a dark home screen, and into iOS — which composites an
    apple-touch-icon onto black.
    """
    canvas = size * SUPERSAMPLE
    image = Image.new("RGB", (canvas, canvas), WHITE)
    side = canvas * scale
    draw_mark(ImageDraw.Draw(image), (canvas - side) / 2, side)
    return image.resize((size, size), Image.LANCZOS)


def svg() -> str:
    """The vector master, as the three source elements over a white ground.

    Written with the artwork's own numbers so that this file and the PNGs beside
    it cannot drift apart.

    No `shape-rendering` hint. The tempting one is `crispEdges`, because at 16 px
    the frame is a sixth of a pixel and antialiases to grey — but it applies to
    a whole subtree, and on the diagonal band it would trade a soft edge at
    every size for a hard one, which is the worse bargain by far. Setting it on
    the two axis-aligned shapes alone would leave the frame's width up to how
    each renderer rounds a sub-pixel stroke, and a frame that rounds to zero is
    a worse 16 px icon than a grey one. The band is what carries the mark at
    that size regardless.
    """
    def points(pairs: tuple[tuple[float, float], ...]) -> str:
        return " ".join(f"{x},{y}" for x, y in pairs)

    x1, y1, x2, y2 = FRAME
    frame = ((x1, y1), (x2, y1), (x2, y2), (x1, y2))
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {SIDE} {SIDE}">
  <title>University of Bayreuth</title>
  <rect width="{SIDE}" height="{SIDE}" fill="#ffffff"/>
  <polyline fill="none" stroke="#000000" stroke-width="{STROKE}" points="{points(RULE)}"/>
  <polygon fill="#009d6d" points="{points(BAND)}"/>
  <polygon fill="none" stroke="#000000" stroke-width="{STROKE}" points="{points(frame)}"/>
</svg>
"""


#: name -> (pixel size, fraction of the icon the mark occupies).
PNGS: dict[str, tuple[int, float]] = {
    "icon-192.png": (192, 1.0),
    "icon-512.png": (512, 1.0),
    "icon-maskable-512.png": (512, MASKABLE_SCALE),
    "apple-touch-icon.png": (180, APPLE_SCALE),
}


def main() -> None:
    console.step("Building the icon set")
    STATIC.mkdir(parents=True, exist_ok=True)

    target = STATIC / "favicon.svg"
    target.write_text(svg(), encoding="utf-8", newline="\n")
    console.info(f"{rel(target)} ({target.stat().st_size:,} B)")

    for name, (size, scale) in PNGS.items():
        target = STATIC / name
        render(size, scale).save(target, "PNG", optimize=True)
        console.info(f"{rel(target)} — {size}x{size}, mark at {scale:.0%} ({target.stat().st_size:,} B)")

    console.table([("files", 1 + len(PNGS)), ("source", "Universität Bayreuth mark")])


if __name__ == "__main__":
    main()
