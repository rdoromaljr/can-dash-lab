#!/usr/bin/env python3
"""
icons.py - vector-drawn automotive tell-tale symbols.

Every icon is drawn with pygame primitives (no image assets), normalized so
`s` is roughly the half-height of the glyph. Shapes follow the ISO 7000 /
ECE R121 tell-tales you actually see in a car cluster.

All functions share the signature: draw_x(surf, cx, cy, s, col)
"""
import math

import pygame


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------
def _poly(surf, col, pts, width=0):
    pygame.draw.polygon(surf, col, [(int(x), int(y)) for x, y in pts], width)


def _line(surf, col, a, b, w=2):
    pygame.draw.line(surf, col, (int(a[0]), int(a[1])),
                     (int(b[0]), int(b[1])), w)


def _arc(surf, col, cx, cy, r, a0, a1, w=2):
    rect = pygame.Rect(int(cx - r), int(cy - r), int(r * 2), int(r * 2))
    pygame.draw.arc(surf, col, rect, math.radians(a0), math.radians(a1), w)


def _bang(surf, col, cx, cy, s, w=3):
    """Exclamation mark, vertically centered on (cx, cy)."""
    _line(surf, col, (cx, cy - s * 0.55), (cx, cy + s * 0.15), w)
    pygame.draw.circle(surf, col, (int(cx), int(cy + s * 0.48)),
                       max(1, int(w * 0.7)))


def _text(surf, s, cx, cy, size, col, bold=True):
    f = pygame.font.SysFont("dejavusansmono,consolas,monospace", size,
                            bold=bold)
    img = f.render(s, True, col)
    surf.blit(img, img.get_rect(center=(int(cx), int(cy))))


# --------------------------------------------------------------------------
# the tell-tales
# --------------------------------------------------------------------------
def icon_abs(surf, cx, cy, s, col):
    """Circle with ABS, flanked by dashed brake arcs."""
    pygame.draw.circle(surf, col, (int(cx), int(cy)), int(s * 0.72), 2)
    _text(surf, "ABS", cx, cy, max(9, int(s * 0.62)), col)
    for side in (-1, 1):
        for i in range(3):
            a0 = -32 + i * 26
            _arc(surf, col, cx, cy, s * 0.95 + 0,
                 (a0 if side > 0 else 180 - a0 - 18),
                 (a0 + 18 if side > 0 else 180 - a0), 2)


def icon_airbag(surf, cx, cy, s, col):
    """Seated occupant (left) facing a deployed bag (right)."""
    # head
    pygame.draw.circle(surf, col, (int(cx - s * 0.52), int(cy - s * 0.34)),
                       int(s * 0.22))
    # torso leaning back, with lap/legs -> reads as a seated person
    _poly(surf, col, [(cx - s * 0.84, cy + s * 0.76),
                      (cx - s * 0.70, cy - s * 0.06),
                      (cx - s * 0.34, cy - s * 0.06),
                      (cx - s * 0.30, cy + s * 0.40),
                      (cx + s * 0.02, cy + s * 0.40),
                      (cx + s * 0.02, cy + s * 0.76)])
    # inflated bag
    pygame.draw.circle(surf, col, (int(cx + s * 0.46), int(cy - s * 0.04)),
                       int(s * 0.44))
    # steering column / dash it deploys from
    _line(surf, col, (cx + s * 0.92, cy - s * 0.70),
          (cx + s * 0.92, cy + s * 0.76), 3)


def icon_esp(surf, cx, cy, s, col):
    """Side-view car above two skid trails."""
    # cabin + body silhouette
    _poly(surf, col, [(cx - s * 0.82, cy + s * 0.10),
                      (cx - s * 0.62, cy - s * 0.22),
                      (cx - s * 0.26, cy - s * 0.54),
                      (cx + s * 0.24, cy - s * 0.54),
                      (cx + s * 0.54, cy - s * 0.22),
                      (cx + s * 0.82, cy - s * 0.14),
                      (cx + s * 0.82, cy + s * 0.10)])
    # wheels make it unmistakably a car
    for sx in (-0.46, 0.50):
        pygame.draw.circle(surf, col, (int(cx + s * sx), int(cy + s * 0.20)),
                           int(s * 0.17))
    # skid trails beneath
    for i in range(2):
        y = cy + s * (0.52 + i * 0.26)
        pts = []
        for k in range(13):
            x = cx - s * 0.86 + k * (s * 1.72 / 12)
            pts.append((x, y + math.sin(k * 1.05) * s * 0.11))
        pygame.draw.lines(surf, col, False,
                          [(int(a), int(b)) for a, b in pts], 2)


def icon_engine(surf, cx, cy, s, col):
    """Engine block silhouette."""
    pts = [
        (cx - s * 0.52, cy - s * 0.18), (cx - s * 0.52, cy - s * 0.46),
        (cx - s * 0.20, cy - s * 0.46), (cx - s * 0.20, cy - s * 0.66),
        (cx + s * 0.20, cy - s * 0.66), (cx + s * 0.20, cy - s * 0.46),
        (cx + s * 0.46, cy - s * 0.46), (cx + s * 0.46, cy - s * 0.22),
        (cx + s * 0.74, cy - s * 0.22), (cx + s * 0.74, cy + s * 0.22),
        (cx + s * 0.46, cy + s * 0.22), (cx + s * 0.46, cy + s * 0.56),
        (cx - s * 0.52, cy + s * 0.56), (cx - s * 0.52, cy + s * 0.22),
        (cx - s * 0.76, cy + s * 0.22), (cx - s * 0.76, cy - s * 0.18),
    ]
    _poly(surf, col, pts)
    # bolt marks
    _line(surf, col, (cx - s * 0.30, cy + s * 0.04),
          (cx + s * 0.22, cy + s * 0.04), 2)


def icon_batt(surf, cx, cy, s, col):
    """Battery with terminals and +/- markings."""
    body = pygame.Rect(int(cx - s * 0.78), int(cy - s * 0.34),
                       int(s * 1.56), int(s * 0.80))
    pygame.draw.rect(surf, col, body, 2, border_radius=2)
    for dx in (-0.44, 0.30):
        t = pygame.Rect(int(cx + s * dx), int(cy - s * 0.52),
                        int(s * 0.14), int(s * 0.18))
        pygame.draw.rect(surf, col, t)
    # plus
    _line(surf, col, (cx - s * 0.52, cy + s * 0.02),
          (cx - s * 0.22, cy + s * 0.02), 2)
    _line(surf, col, (cx - s * 0.37, cy - s * 0.13),
          (cx - s * 0.37, cy + s * 0.17), 2)
    # minus
    _line(surf, col, (cx + s * 0.22, cy + s * 0.02),
          (cx + s * 0.52, cy + s * 0.02), 2)


def icon_oil(surf, cx, cy, s, col):
    """Oil can with a drip."""
    _poly(surf, col, [(cx - s * 0.76, cy + s * 0.30),
                      (cx - s * 0.76, cy - s * 0.14),
                      (cx - s * 0.30, cy - s * 0.14),
                      (cx - s * 0.10, cy - s * 0.40),
                      (cx + s * 0.26, cy - s * 0.40),
                      (cx + s * 0.26, cy - s * 0.14),
                      (cx + s * 0.62, cy + s * 0.30)])
    # spout
    _line(surf, col, (cx + s * 0.26, cy - s * 0.22),
          (cx + s * 0.86, cy - s * 0.52), 3)
    # drip
    pygame.draw.circle(surf, col, (int(cx + s * 0.06), int(cy + s * 0.62)),
                       max(2, int(s * 0.14)))


def icon_coolant(surf, cx, cy, s, col):
    """Thermometer floating on wavy coolant."""
    _line(surf, col, (cx, cy - s * 0.62), (cx, cy + s * 0.12), 3)
    pygame.draw.circle(surf, col, (int(cx), int(cy + s * 0.24)),
                       int(s * 0.26))
    for i in range(3):
        _line(surf, col, (cx + s * 0.12, cy - s * 0.46 + i * s * 0.22),
              (cx + s * 0.40, cy - s * 0.46 + i * s * 0.22), 2)
    for i in range(2):
        y = cy + s * (0.60 + i * 0.24)
        pts = []
        for k in range(13):
            x = cx - s * 0.86 + k * (s * 1.72 / 12)
            pts.append((x, y + math.sin(k * 1.1) * s * 0.10))
        pygame.draw.lines(surf, col, False,
                          [(int(a), int(b)) for a, b in pts], 2)


def icon_tpms(surf, cx, cy, s, col):
    """Tire cross-section with a bang."""
    _arc(surf, col, cx, cy - s * 0.02, s * 0.80, 20, 160, 3)
    _line(surf, col, (cx - s * 0.76, cy + s * 0.26),
          (cx - s * 0.76, cy + s * 0.58), 3)
    _line(surf, col, (cx + s * 0.76, cy + s * 0.26),
          (cx + s * 0.76, cy + s * 0.58), 3)
    _line(surf, col, (cx - s * 0.90, cy + s * 0.62),
          (cx + s * 0.90, cy + s * 0.62), 3)
    # tread ticks
    for i in range(-2, 3):
        _line(surf, col, (cx + i * s * 0.30, cy + s * 0.30),
              (cx + i * s * 0.30, cy + s * 0.52), 2)
    _bang(surf, col, cx, cy - s * 0.06, s * 0.70, 3)


def icon_brake(surf, cx, cy, s, col):
    """(!) between brake-disc parentheses."""
    pygame.draw.circle(surf, col, (int(cx), int(cy)), int(s * 0.60), 2)
    _bang(surf, col, cx, cy, s * 0.62, 3)
    _arc(surf, col, cx, cy, s * 0.92, 40, 140, 3)
    _arc(surf, col, cx, cy, s * 0.92, 220, 320, 3)


def icon_belt(surf, cx, cy, s, col, bg=(10, 12, 16)):
    """Seated occupant with the belt cut through the torso in negative space."""
    pygame.draw.circle(surf, col, (int(cx - s * 0.16), int(cy - s * 0.50)),
                       int(s * 0.23))
    # torso + lap
    _poly(surf, col, [(cx - s * 0.56, cy + s * 0.74),
                      (cx - s * 0.48, cy - s * 0.14),
                      (cx + s * 0.16, cy - s * 0.14),
                      (cx + s * 0.34, cy + s * 0.74)])
    # belt drawn in background colour so it reads as a strap across the body
    pygame.draw.line(surf, bg,
                     (int(cx - s * 0.62), int(cy + s * 0.46)),
                     (int(cx + s * 0.30), int(cy - s * 0.16)), 7)
    # then the strap itself, extending past the body on both ends
    _line(surf, col, (cx - s * 0.74, cy + s * 0.56),
          (cx + s * 0.44, cy - s * 0.26), 4)


def icon_door(surf, cx, cy, s, col):
    """Car from above with both doors swung open (outlined, with gaps)."""
    body = pygame.Rect(int(cx - s * 0.30), int(cy - s * 0.70),
                       int(s * 0.60), int(s * 1.40))
    pygame.draw.rect(surf, col, body, 3, border_radius=int(s * 0.20))
    # roof line so the body reads as a car, not a pill
    _line(surf, col, (cx - s * 0.30, cy - s * 0.16),
          (cx + s * 0.30, cy - s * 0.16), 2)
    for sx in (-1, 1):
        # hinge at the body, swung outward, drawn as an outline with a gap
        _poly(surf, col, [(cx + sx * s * 0.40, cy - s * 0.30),
                          (cx + sx * s * 1.00, cy - s * 0.12),
                          (cx + sx * s * 1.00, cy + s * 0.26),
                          (cx + sx * s * 0.40, cy + s * 0.16)], 3)


def icon_fuel(surf, cx, cy, s, col):
    """Fuel pump."""
    body = pygame.Rect(int(cx - s * 0.70), int(cy - s * 0.62),
                       int(s * 0.90), int(s * 1.24))
    pygame.draw.rect(surf, col, body, 2, border_radius=2)
    _line(surf, col, (cx - s * 0.54, cy - s * 0.30),
          (cx + s * 0.04, cy - s * 0.30), 6)
    _line(surf, col, (cx + s * 0.20, cy + s * 0.62),
          (cx + s * 0.62, cy + s * 0.62), 2)
    _line(surf, col, (cx + s * 0.62, cy + s * 0.62),
          (cx + s * 0.62, cy - s * 0.22), 2)
    _arc(surf, col, cx + s * 0.44, cy - s * 0.30, s * 0.20, -90, 90, 2)


def icon_highbeam(surf, cx, cy, s, col):
    """Headlight with straight beams."""
    _poly(surf, col, [(cx - s * 0.10, cy - s * 0.56),
                      (cx - s * 0.10, cy + s * 0.56),
                      (cx - s * 0.62, cy + s * 0.56),
                      (cx - s * 0.62, cy - s * 0.56)])
    _arc(surf, col, cx - s * 0.10, cy, s * 0.56, -90, 90, 3)
    for i in range(4):
        y = cy - s * 0.42 + i * s * 0.28
        _line(surf, col, (cx + s * 0.22, y), (cx + s * 0.92, y), 2)


def icon_arrow(surf, cx, cy, s, col, left=True):
    d = -1 if left else 1
    _poly(surf, col, [(cx + d * s * 0.92, cy),
                      (cx + d * s * 0.10, cy - s * 0.80),
                      (cx + d * s * 0.10, cy - s * 0.34),
                      (cx - d * s * 0.86, cy - s * 0.34),
                      (cx - d * s * 0.86, cy + s * 0.34),
                      (cx + d * s * 0.10, cy + s * 0.34),
                      (cx + d * s * 0.10, cy + s * 0.80)])


ICONS = {
    "ABS": icon_abs,
    "AIRBAG": icon_airbag,
    "ESP/TCS": icon_esp,
    "CHECK ENG": icon_engine,
    "BATT": icon_batt,
    "OIL": icon_oil,
    "COOLANT": icon_coolant,
    "TPMS": icon_tpms,
    "BRAKE!": icon_brake,
    "BRAKE": icon_brake,
    "FUEL LOW": icon_fuel,
    "BELT": icon_belt,
    "DOOR": icon_door,
    "HIGH BEAM": icon_highbeam,
}


def draw_icon(surf, name, cx, cy, s, col, bg=(10, 12, 16)):
    fn = ICONS.get(name)
    if fn is None:
        _text(surf, name[:3], cx, cy, max(9, int(s * 0.7)), col)
        return False
    try:
        fn(surf, cx, cy, s, col, bg)
    except TypeError:
        fn(surf, cx, cy, s, col)
    return True
