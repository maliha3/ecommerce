"""Procedurally drawn product photos for the mock catalogue.

Real product shots need a photographer (or the supplier's own media kit).
These stand in: each item is a silhouette rendered with a material finish,
a vertical shade and a soft drop shadow, so the storefront looks like a real
shop while you wait for the real photographs. Output is deterministic.

Everything is drawn with Pillow — no downloads, no licensing, no third-party
product imagery.

    from store.mockimages import render
    render("handbag", "#b03a5b", finish="leather", seed=3).save("bag.jpg")

Shapes: see SHAPES. Finishes: "fabric", "leather", "metal".
"""
from __future__ import annotations

import math
import random

from PIL import Image, ImageChops, ImageDraw, ImageFilter

SIZE = 1000

# Kinds that make up the body — they build the shadow/clipping mask.
# "line" and "dot" are details drawn crisply on top afterwards.
_FILL_KINDS = {"poly", "ellipse", "pieslice", "round_rect", "ring"}


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------


def _rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))


def _tone(rgb, amount: float):
    """Lighten (amount > 0) or darken (amount < 0) a colour."""
    if amount >= 0:
        return tuple(round(c + (255 - c) * amount) for c in rgb)
    return tuple(round(c * (1 + amount)) for c in rgb)


def _is_dark(rgb) -> bool:
    """True for materials too dark to show a darker seam."""
    return (rgb[0] * 299 + rgb[1] * 587 + rgb[2] * 114) / 1000 < 70


def _mirror(points):
    return [(SIZE - x, y) for x, y in points]


def _bezier(p0, p1, p2, steps=26):
    """Quadratic curve, for straps, chains and shoe lines."""
    out = []
    for i in range(steps + 1):
        t = i / steps
        u = 1 - t
        out.append(
            (
                u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0],
                u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1],
            )
        )
    return out


def _outline(segments, steps=18):
    """Chain quadratic segments into one smooth closed outline.

    Each segment is (start, control, end). Straight runs just use the
    midpoint as the control.
    """
    points = []
    for start, control, end in segments:
        points.extend(_bezier(start, control, end, steps)[:-1])
    return points


def _inset(points, factor, cx=500, cy=500):
    """Shrink an outline toward a centre, for a sole edge or a trim line."""
    return [
        (cx + (x - cx) * factor, cy + (y - cy) * factor) for x, y in points
    ]


def _chain_links(curve, radius=11, tone=0.12, every=2):
    """Render a curve as discrete links, so a strap reads as a chain."""
    return [
        {"kind": "dot", "xy": point, "r": radius, "tone": tone}
        for i, point in enumerate(curve)
        if i % every == 0
    ]


# --------------------------------------------------------------------------
# bags
# --------------------------------------------------------------------------


def _handbag():
    body = [(258, 412), (742, 412), (694, 806), (306, 806)]
    handle = _bezier((382, 418), (500, 212), (618, 418))
    return [
        {"kind": "poly", "points": body},
        {"kind": "poly", "points": [(258, 412), (742, 412), (742, 466), (258, 466)],
         "tone": -0.12},
        {"kind": "line", "points": handle, "tone": -0.18, "width": 19},
        {"kind": "round_rect", "box": (466, 428, 534, 486), "radius": 12,
         "colour": "#c9a227"},
        {"kind": "line", "points": [(316, 788), (684, 788)], "tone": -0.14, "width": 6},
        {"kind": "line", "points": [(300, 480), (268, 790)], "tone": -0.14, "width": 5},
        {"kind": "line", "points": [(700, 480), (732, 790)], "tone": -0.14, "width": 5},
    ]


def _flap_bag():
    flap = [(282, 452), (718, 452), (718, 604), (282, 604)]
    strap = _bezier((336, 462), (500, 236), (664, 462))
    elements = [
        {"kind": "round_rect", "box": (282, 452, 718, 776), "radius": 26},
        {"kind": "poly", "points": flap, "tone": -0.09},
    ]
    elements += _chain_links(strap, radius=12, tone=0.3)
    elements += [
        {"kind": "round_rect", "box": (456, 572, 544, 636), "radius": 10,
         "colour": "#c9a227"},
        {"kind": "line", "points": [(282, 604), (718, 604)], "tone": -0.22, "width": 6},
    ]
    # Quilting: a loose diamond lattice across the body.
    for offset in range(-300, 460, 76):
        elements.append(
            {"kind": "line", "points": [(302 + offset, 772), (482 + offset, 612)],
             "tone": -0.13, "width": 4, "clip": True}
        )
        elements.append(
            {"kind": "line", "points": [(698 - offset, 772), (518 - offset, 612)],
             "tone": -0.13, "width": 4, "clip": True}
        )
    return elements


# --------------------------------------------------------------------------
# shoes
# --------------------------------------------------------------------------


def _heel():
    """Court shoe from above, to match the trainer.

    A pointed toe, a wide topline opening and no laces is what separates it
    from the trainer at a glance; the stiletto shows as a tab past the heel.
    """
    half = [
        ((500, 148), (430, 170), (396, 276)),
        ((396, 276), (366, 368), (382, 452)),
        ((382, 452), (398, 556), (414, 648)),
        ((414, 648), (424, 744), (452, 796)),
        ((452, 796), (474, 822), (500, 824)),
    ]
    left = _outline(half)
    body = left + _mirror(left)[::-1]
    return [
        {"kind": "round_rect", "box": (470, 760, 530, 866), "radius": 18,
         "tone": -0.30},
        {"kind": "poly", "points": body},
        {"kind": "poly", "points": _inset(body, 0.94), "tone": 0.05},
        # The topline opening — the single clearest "this is a shoe" cue.
        {"kind": "ellipse", "box": (420, 416, 580, 744), "tone": -0.40},
        {"kind": "ring", "box": (420, 416, 580, 744), "width": 9, "tone": 0.16},
        {"kind": "line", "points": _bezier((432, 300), (500, 252), (568, 300)),
         "tone": -0.20, "width": 7, "clip": True},
    ]


def _sneaker():
    """Trainer seen from above — symmetric, and unmistakably a shoe."""
    half = [
        ((500, 170), (408, 188), (376, 306)),
        ((376, 306), (356, 400), (370, 486)),
        ((370, 486), (384, 580), (398, 660)),
        ((398, 660), (410, 760), (446, 808)),
        ((446, 808), (470, 836), (500, 838)),
    ]
    left = _outline(half)
    body = left + _mirror(left)[::-1]
    upper = _inset(body, 0.945)
    return [
        # White cup sole, with the upper sitting just inside it.
        {"kind": "poly", "points": body, "colour": "#f6f5f1"},
        {"kind": "poly", "points": upper},
        # Foot opening and tongue.
        {"kind": "ellipse", "box": (412, 468, 588, 772), "tone": -0.34},
        {"kind": "round_rect", "box": (438, 424, 562, 566), "radius": 46,
         "tone": -0.10},
        {"kind": "line", "points": _bezier((404, 300), (500, 258), (596, 300)),
         "tone": -0.22, "width": 8, "clip": True},
        {"kind": "line", "points": _bezier((392, 430), (500, 396), (608, 430)),
         "tone": -0.18, "width": 7, "clip": True},
    ] + [
        # Eyelets and crossed laces down the throat.
        {"kind": "dot", "xy": (x, y), "r": 7, "tone": -0.40}
        for y in (452, 504, 556)
        for x in (446, 554)
    ] + [
        {"kind": "line", "points": [(446, 452), (554, 504)], "colour": "#ffffff",
         "width": 7},
        {"kind": "line", "points": [(554, 452), (446, 504)], "colour": "#ffffff",
         "width": 7},
        {"kind": "line", "points": [(446, 504), (554, 556)], "colour": "#ffffff",
         "width": 7},
        {"kind": "line", "points": [(554, 504), (446, 556)], "colour": "#ffffff",
         "width": 7},
    ]


# --------------------------------------------------------------------------
# jewellery
# --------------------------------------------------------------------------


def _necklace():
    curve = _bezier((290, 286), (500, 724), (710, 286), steps=40)
    elements = _chain_links(curve, radius=13, tone=0.16, every=1)
    elements += [
        {"kind": "ellipse", "box": (470, 580, 530, 640), "tone": -0.10},
        {"kind": "poly", "points": [(500, 612), (574, 700), (500, 812), (426, 700)],
         "tone": 0.05},
        {"kind": "poly", "points": [(500, 648), (540, 702), (500, 766), (460, 702)],
         "colour": "#ffffff"},
    ]
    return elements


def _ring():
    return [
        {"kind": "ring", "box": (328, 376, 672, 720), "width": 54},
        {"kind": "ring", "box": (348, 396, 652, 700), "width": 10, "tone": 0.3},
        # Claw-set stone above the band.
        {"kind": "poly", "points": [(500, 212), (596, 318), (500, 412), (404, 318)],
         "colour": "#eef3f7"},
        {"kind": "poly", "points": [(500, 212), (596, 318), (500, 318)],
         "colour": "#cfdce6"},
        {"kind": "poly", "points": [(500, 412), (404, 318), (500, 318)],
         "colour": "#dfe9f1"},
        {"kind": "line", "points": [(404, 318), (596, 318)], "colour": "#b9cad8",
         "width": 5},
    ]


def _bangle():
    return [
        {"kind": "ring", "box": (236, 236, 764, 764), "width": 74},
        {"kind": "ring", "box": (258, 258, 742, 742), "width": 11, "tone": 0.34},
        {"kind": "ring", "box": (300, 300, 700, 700), "width": 9, "tone": -0.26},
    ]


def _chain():
    """A rope chain with no pendant — heavier links than the pendant chain."""
    curve = _bezier((276, 272), (500, 772), (724, 272), steps=44)
    elements = _chain_links(curve, radius=17, tone=0.14, every=1)
    elements += [
        {"kind": "ring", "box": (690, 236, 758, 304), "width": 15, "tone": 0.2},
        {"kind": "ring", "box": (242, 236, 310, 304), "width": 15, "tone": 0.2},
    ]
    return elements


def _bangle_pair():
    """Two bangles, overlapping — so a pair does not look like a single."""
    return [
        {"kind": "ring", "box": (172, 290, 612, 730), "width": 62},
        {"kind": "ring", "box": (190, 308, 594, 712), "width": 10, "tone": 0.3},
        {"kind": "ring", "box": (388, 290, 828, 730), "width": 62, "tone": -0.06},
        {"kind": "ring", "box": (406, 308, 810, 712), "width": 10, "tone": 0.28},
        {"kind": "ring", "box": (446, 348, 770, 672), "width": 8, "tone": -0.24},
    ]


def _earrings():
    elements = []
    for x in (372, 628):
        elements += [
            {"kind": "ellipse", "box": (x - 30, 288, x + 30, 348)},
            {"kind": "line", "points": [(x, 340), (x, 410)], "tone": -0.08, "width": 9},
            {"kind": "ellipse", "box": (x - 62, 400, x + 62, 592)},
            {"kind": "ellipse", "box": (x - 34, 436, x + 34, 520), "tone": 0.34},
            {"kind": "dot", "xy": (x, 306), "r": 11, "colour": "#ffffff"},
        ]
    return elements


# --------------------------------------------------------------------------
# watches and tech
# --------------------------------------------------------------------------


def _watch():
    return [
        {"kind": "poly", "points": [(414, 196), (586, 196), (574, 332), (426, 332)],
         "tone": -0.16},
        {"kind": "poly", "points": [(426, 672), (574, 672), (586, 812), (414, 812)],
         "tone": -0.16},
        {"kind": "round_rect", "box": (372, 300, 628, 704), "radius": 72},
        {"kind": "round_rect", "box": (396, 324, 604, 680), "radius": 56,
         "colour": "#0b0b0d"},
        {"kind": "round_rect", "box": (436, 372, 564, 408), "radius": 14,
         "colour": "#2f3238"},
        {"kind": "round_rect", "box": (436, 432, 520, 468), "radius": 14,
         "colour": "#3f8f6a"},
        {"kind": "round_rect", "box": (436, 492, 564, 596), "radius": 18,
         "colour": "#1b1d21"},
        {"kind": "round_rect", "box": (624, 426, 646, 506), "radius": 10, "tone": -0.2},
        {"kind": "line", "points": [(414, 206), (586, 206)], "tone": -0.3, "width": 5},
        {"kind": "line", "points": [(414, 802), (586, 802)], "tone": -0.3, "width": 5},
    ]


def _earbuds():
    elements = []
    for x in (382, 618):
        elements += [
            {"kind": "ellipse", "box": (x - 74, 272, x + 74, 420)},
            {"kind": "round_rect", "box": (x - 32, 388, x + 32, 648), "radius": 30},
            {"kind": "ellipse", "box": (x - 44, 310, x + 20, 372), "tone": -0.16},
            {"kind": "line", "points": [(x - 22, 612), (x + 22, 612)], "tone": -0.14,
             "width": 6},
        ]
    return elements


SHAPES = {
    "handbag": _handbag,
    "flap_bag": _flap_bag,
    "heel": _heel,
    "sneaker": _sneaker,
    "necklace": _necklace,
    "ring": _ring,
    "bangle": _bangle,
    "bangle_pair": _bangle_pair,
    "chain": _chain,
    "earrings": _earrings,
    "watch": _watch,
    "earbuds": _earbuds,
}


# --------------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------------


def _background() -> Image.Image:
    gradient = Image.linear_gradient("L").resize((SIZE, SIZE))
    return Image.composite(
        Image.new("RGB", (SIZE, SIZE), (233, 231, 226)),
        Image.new("RGB", (SIZE, SIZE), (247, 246, 243)),
        gradient,
    )


def _grain(seed: int) -> Image.Image:
    """Seeded grain, drawn small and scaled up so it reads as a weave."""
    rnd = random.Random(seed)
    side = 230
    data = bytes(rnd.randrange(106, 150) for _ in range(side * side))
    return (
        Image.frombytes("L", (side, side), data)
        .resize((SIZE, SIZE), Image.BILINEAR)
        .convert("RGB")
    )


def _sheen() -> Image.Image:
    """Horizontal highlight bands — what makes metal look like metal."""
    row = bytearray()
    for x in range(SIZE):
        t = x / SIZE
        value = 116
        value += 118 * math.exp(-(((t - 0.33) ** 2) / 0.011))
        value += 74 * math.exp(-(((t - 0.63) ** 2) / 0.020))
        value += 40 * math.exp(-(((t - 0.86) ** 2) / 0.006))
        row.append(max(0, min(255, int(value))))
    return (
        Image.frombytes("L", (SIZE, 1), bytes(row))
        .resize((SIZE, SIZE))
        .convert("RGB")
    )


def _shade(strength: float) -> Image.Image:
    return (
        Image.linear_gradient("L")
        .point(lambda v: 255 - int(v * strength))
        .resize((SIZE, SIZE))
        .convert("RGB")
    )


def _wanted(element, pass_name: str) -> bool:
    """Which of the three passes an element belongs to.

    "mask"     - the silhouette, for the shadow and for clipping
    "material" - body panels, plus details marked ``clip`` so that things
                 like quilting cannot spill outside the item
    "detail"   - crisp overlays drawn last (laces, clasps, stitching)
    """
    is_body = element["kind"] in _FILL_KINDS
    if pass_name == "mask":
        return is_body
    if pass_name == "material":
        return is_body or element.get("clip", False)
    return not is_body and not element.get("clip", False)


def _draw(canvas, element, base, pass_name, flat=None):
    draw = ImageDraw.Draw(canvas)
    kind = element["kind"]

    if not _wanted(element, pass_name):
        return

    if flat is not None:
        colour = flat
    elif "colour" in element:
        colour = _rgb(element["colour"])
    else:
        amount = element.get("tone", 0.0)
        if _is_dark(base):
            # Seams on black leather read as highlights, not shadows.
            amount = -amount * 0.85
        colour = _tone(base, amount)

    if kind == "poly":
        draw.polygon(element["points"], fill=colour)
    elif kind == "ellipse":
        draw.ellipse(element["box"], fill=colour)
    elif kind == "pieslice":
        draw.pieslice(element["box"], element["start"], element["end"], fill=colour)
    elif kind == "round_rect":
        draw.rounded_rectangle(element["box"], element.get("radius", 20), fill=colour)
    elif kind == "ring":
        draw.ellipse(element["box"], outline=colour, width=element["width"])
    elif kind == "line":
        draw.line(
            [tuple(p) for p in element["points"]],
            fill=colour,
            width=element.get("width", 5),
            joint="curve",
        )
    elif kind == "dot":
        x, y = element["xy"]
        r = element["r"]
        draw.ellipse((x - r, y - r, x + r, y + r), fill=colour)


def render(shape: str, colour: str, finish: str = "fabric", seed: int = 0):
    """Render one product and return an RGB image."""
    if shape not in SHAPES:
        raise ValueError(f"unknown shape {shape!r}; try {sorted(SHAPES)}")

    base = _rgb(colour)
    elements = SHAPES[shape]()
    canvas = _background()

    # Silhouette: drives the drop shadow and clips the material layer.
    mask = Image.new("L", (SIZE, SIZE), 0)
    for element in elements:
        _draw(mask, element, base, "mask", flat=255)

    shadow = Image.new("L", (SIZE, SIZE), 0)
    shadow.paste(mask.filter(ImageFilter.GaussianBlur(26)), (0, 18))
    canvas.paste(
        Image.new("RGB", (SIZE, SIZE), (90, 86, 80)),
        (0, 0),
        shadow.point(lambda v: int(v * 0.32)),
    )

    material = Image.new("RGB", (SIZE, SIZE), base)
    for element in elements:
        _draw(material, element, base, "material")

    if finish == "metal":
        material = Image.blend(material, ImageChops.overlay(material, _sheen()), 0.62)
        material = ImageChops.multiply(material, _shade(0.10))
    elif finish == "leather":
        material = Image.blend(material, ImageChops.overlay(material, _grain(seed)), 0.14)
        material = ImageChops.multiply(material, _shade(0.26))
    else:
        material = Image.blend(material, ImageChops.overlay(material, _grain(seed)), 0.28)
        material = ImageChops.multiply(material, _shade(0.20))

    canvas.paste(material, (0, 0), mask)

    for element in elements:
        _draw(canvas, element, base, "detail")

    return canvas
