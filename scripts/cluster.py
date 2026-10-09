#!/usr/bin/env python3
"""
cluster.py - realistic instrument cluster rendering.

Layout follows a real binnacle rather than a dashboard of boxes:

      ┌──────────────────────────────────────────────┐
      │      ((  tell-tale strip across the top  ))  │
      │   ╭─────────╮   ┌──────────┐   ╭─────────╮   │
      │   │  TACHO  │   │   info   │   │  SPEEDO │   │
      │   │   ( )   │   │  gear    │   │   ( )   │   │
      │   ╰─────────╯   │  odo     │   ╰─────────╯   │
      │                 └──────────┘                 │
      │        fuel bar          temp bar            │
      └──────────────────────────────────────────────┘

Warning symbols live INSIDE the dial faces and in the top strip, the way a
real cluster does it.
"""
import math
import time

import pygame

from icons import draw_icon, icon_arrow
from ui import text, font

# --- cluster palette (warmer, more automotive than the old flat panel) ----
BEZEL_OUT = (26, 29, 36)
BEZEL_IN = (14, 16, 21)
FACE = (17, 19, 25)
FACE_EDGE = (46, 52, 64)
TICK = (150, 160, 176)
TICK_DIM = (74, 82, 96)
NEEDLE = (236, 78, 72)
NEEDLE_GLOW = (120, 32, 30)
TXT = (232, 238, 246)
MUTED = (126, 138, 156)
DIM = (52, 58, 70)
CYAN = (64, 206, 232)
GREEN = (72, 222, 142)
AMBER = (248, 178, 56)
RED = (238, 80, 78)
BG = (8, 9, 12)


def binnacle(surf, rect):
    """Arched instrument hood: wide rounded shell, darker recessed face.

    Mirrors a real cluster housing - the top corners sweep up over the dials
    and the whole face sits inside a raised bezel.
    """
    # outer hood with a strong arch on top
    hood = rect.inflate(0, 0)
    pygame.draw.rect(surf, (36, 40, 49), hood,
                     border_top_left_radius=int(rect.h * 0.46),
                     border_top_right_radius=int(rect.h * 0.46),
                     border_bottom_left_radius=26,
                     border_bottom_right_radius=26)
    # bezel highlight
    pygame.draw.rect(surf, (72, 79, 94), hood, width=2,
                     border_top_left_radius=int(rect.h * 0.46),
                     border_top_right_radius=int(rect.h * 0.46),
                     border_bottom_left_radius=26,
                     border_bottom_right_radius=26)
    # recessed inner face
    inner = rect.inflate(-20, -20)
    pygame.draw.rect(surf, BEZEL_IN, inner,
                     border_top_left_radius=int(inner.h * 0.42),
                     border_top_right_radius=int(inner.h * 0.42),
                     border_bottom_left_radius=18,
                     border_bottom_right_radius=18)
    pygame.draw.rect(surf, (16, 18, 23), inner, width=1,
                     border_top_left_radius=int(inner.h * 0.42),
                     border_top_right_radius=int(inner.h * 0.42),
                     border_bottom_left_radius=18,
                     border_bottom_right_radius=18)
    return inner


# keep the old name working
def vignette(surf, rect):
    return binnacle(surf, rect)


def dial(surf, cx, cy, r, value, vmin, vmax, major, label, unit,
         redline=None, accent=CYAN, decimals=0, minor_per_major=5,
         sub_text=None):
    """A round gauge with a swept needle, drawn to look like a real dial."""
    start, end = 212.0, -32.0          # leaves the gap at the bottom
    span = start - end

    # face
    pygame.draw.circle(surf, (30, 34, 42), (cx, cy), r + 6)
    pygame.draw.circle(surf, FACE, (cx, cy), r)
    pygame.draw.circle(surf, FACE_EDGE, (cx, cy), r, 2)
    pygame.draw.circle(surf, (24, 27, 34), (cx, cy), r - 3, 1)

    frac = 0.0 if vmax <= vmin else (value - vmin) / (vmax - vmin)
    frac = max(0.0, min(1.0, frac))

    # Outer ring of chunky dashes (Librow style) with numerals inside it.
    total_minor = major * minor_per_major
    for i in range(total_minor + 1):
        f = i / total_minor
        ang = math.radians(start - span * f)
        val = vmin + (vmax - vmin) * f
        is_major = (i % minor_per_major == 0)
        hot = redline is not None and val >= redline
        col = RED if hot else (TICK if is_major else TICK_DIM)
        _c, _s = math.cos(ang), math.sin(ang)
        if is_major:
            r0, r1, w = r - 20, r - 4, 4
        else:
            r0, r1, w = r - 14, r - 5, 2
        pygame.draw.line(surf, col, (cx + r0 * _c, cy - r0 * _s),
                         (cx + r1 * _c, cy - r1 * _s), w)
        if is_major:
            rt = r - 38
            text(surf, f"{val:.0f}", cx + rt * _c, cy - rt * _s,
                 15, RED if hot else TICK, center=True, bold=True)

    # redline band
    if redline is not None and vmax > vmin:
        rf = (redline - vmin) / (vmax - vmin)
        if 0.0 <= rf < 1.0:
            rect = pygame.Rect(cx - r + 6, cy - r + 6, (r - 6) * 2, (r - 6) * 2)
            pygame.draw.arc(surf, RED, rect,
                            math.radians(end), math.radians(start - span * rf),
                            5)

    # swept value arc
    if frac > 0.002:
        rect = pygame.Rect(cx - r + 13, cy - r + 13, (r - 13) * 2,
                           (r - 13) * 2)
        hot = redline is not None and value >= redline
        pygame.draw.arc(surf, RED if hot else accent, rect,
                        math.radians(start - span * frac),
                        math.radians(start), 4)

    # Odometer / clock sits high in the face, like a real cluster.
    if sub_text:
        text(surf, sub_text, cx, cy - r * 0.40, 13, (150, 160, 176),
             center=True)
    text(surf, label, cx, cy - r * 0.44, 10, (82, 90, 106), bold=True,
         center=True)
    fmt = f"{{:.{decimals}f}}"
    text(surf, fmt.format(value), cx, cy + r * 0.33, 27, TXT, bold=True,
         center=True)
    if unit:
        text(surf, unit, cx, cy + r * 0.54, 11, MUTED, center=True)

    # needle
    ang = math.radians(start - span * frac)
    nl = r - 20
    tail = 16
    _c, _s = math.cos(ang), math.sin(ang)
    tip = (cx + nl * _c, cy - nl * _s)
    back = (cx - tail * _c, cy + tail * _s)
    perp = ang + math.pi / 2
    pc, ps = math.cos(perp), math.sin(perp)
    hot = redline is not None and value >= redline
    ncol = RED if hot else NEEDLE
    for w, c in ((7, NEEDLE_GLOW), (4, ncol)):
        _poly = [(cx + w * pc, cy - w * ps), (cx - w * pc, cy + w * ps), tip]
        pygame.draw.polygon(surf, c, [(int(a), int(b)) for a, b in _poly])
    pygame.draw.line(surf, ncol, (int(cx), int(cy)),
                     (int(back[0]), int(back[1])), 5)
    pygame.draw.circle(surf, (38, 42, 52), (cx, cy), 15)
    pygame.draw.circle(surf, ncol, (cx, cy), 15, 2)
    pygame.draw.circle(surf, (20, 22, 28), (cx, cy), 7)


def dial_lamps(surf, cx, cy, r, items):
    """Warning symbols arranged INSIDE the lower arc of a dial face."""
    n = len(items)
    if not n:
        return
    # Row across the bottom dead-zone of the face. The needle sweep stops at
    # 212deg/-32deg, so this band is never crossed and nothing collides.
    gap = r * 0.32
    total = gap * (n - 1)
    y = cy + r * 0.74
    for i, (name, on, col) in enumerate(items):
        px = cx - total / 2 + gap * i
        draw_icon(surf, name, px, y, r * 0.105,
                  col if on else DIM, bg=FACE)


def strip_lamps(surf, rect, items, bg=BEZEL_IN):
    """Top tell-tale strip: evenly spaced icons, lit ones in colour."""
    if not items:
        return
    n = len(items)
    step = rect.w / float(n)
    for i, (name, on, col) in enumerate(items):
        cx = rect.x + step * (i + 0.5)
        cy = rect.centery
        if on:
            rad = int(rect.h * 0.46)
            glow = pygame.Surface((rad * 2, rad * 2), pygame.SRCALPHA)
            for k, a in ((rad, 26), (int(rad * 0.72), 34)):
                pygame.draw.circle(glow, (*col, a), (rad, rad), k)
            surf.blit(glow, (int(cx - rad), int(cy - rad)))
        draw_icon(surf, name, cx, cy, rect.h * 0.30,
                  col if on else DIM, bg=bg)


def seg_bar(surf, rect, frac, icon, col=GREEN, warn=0.15, segs=12,
            left_label="", mid_label="", right_label="", flip=False):
    """Segmented fuel/temperature bar, Librow style.

    A row of discrete blocks with the symbol at one end and E / 1/2 / F
    (or 40 / 80 / 120) captions underneath.
    """
    frac = max(0.0, min(1.0, frac))
    low = frac < warn
    icol = RED if low else (150, 160, 176)

    ix = rect.x - 16 if not flip else rect.right + 16
    draw_icon(surf, icon, ix, rect.centery, 11, icol, bg=BEZEL_IN)

    gap = 2
    sw = (rect.w - gap * (segs - 1)) / float(segs)
    lit = int(round(frac * segs))
    for i in range(segs):
        x = rect.x + i * (sw + gap)
        seg = pygame.Rect(int(x), rect.y, int(sw), rect.h)
        on = (i < lit) if not flip else (i >= segs - lit)
        if on:
            pygame.draw.rect(surf, RED if low else col, seg)
        else:
            pygame.draw.rect(surf, (38, 43, 54), seg, 1)

    y = rect.bottom + 9
    if left_label:
        text(surf, left_label, rect.x, y, 10, TICK_DIM)
    if mid_label:
        text(surf, mid_label, rect.centerx, y, 10, TICK_DIM, center=True)
    if right_label:
        text(surf, right_label, rect.right, y, 10, TICK_DIM, right=True)


def bar_gauge(surf, rect, frac, label, icon, col=GREEN, warn=0.15,
              ticks=4):
    """Horizontal fuel/temp bar with its symbol at the left, E...F ticks."""
    frac = max(0.0, min(1.0, frac))
    low = frac < warn
    draw_icon(surf, icon, rect.x - 22, rect.centery, 13,
              RED if low else MUTED, bg=BEZEL_IN)

    track = pygame.Rect(rect.x, rect.centery - 7, rect.w, 14)
    pygame.draw.rect(surf, (20, 23, 29), track, border_radius=7)
    pygame.draw.rect(surf, FACE_EDGE, track, width=1, border_radius=7)
    if frac > 0:
        fill = pygame.Rect(track.x + 2, track.y + 2,
                           max(4, int((track.w - 4) * frac)), track.h - 4)
        pygame.draw.rect(surf, RED if low else col, fill, border_radius=5)
    for i in range(ticks + 1):
        x = track.x + track.w * i / ticks
        h = 6 if i in (0, ticks) else 3
        pygame.draw.line(surf, TICK_DIM, (x, track.bottom + 3),
                         (x, track.bottom + 3 + h), 1)
    text(surf, label, rect.centerx, rect.y - 9, 11, MUTED, center=True,
         bold=True)
