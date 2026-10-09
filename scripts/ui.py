#!/usr/bin/env python3
"""
ui.py - drawing primitives shared by the cluster and the control panel.

Pure pygame, no images: everything is vector-drawn so it scales cleanly and
there are no asset files to ship.
"""
import math

import pygame

# --- palette ---------------------------------------------------------------
BG        = (10, 12, 16)
PANEL     = (18, 21, 27)
EDGE      = (38, 44, 54)
TEXT      = (226, 232, 240)
MUTED     = (122, 134, 152)
CYAN      = (56, 208, 232)
GREEN     = (64, 220, 140)
AMBER     = (248, 176, 56)
RED       = (238, 78, 78)
DIM       = (44, 50, 62)


def font(size, bold=False):
    key = (size, bold)
    if key not in _FONTS:
        name = "dejavusansmono,consolas,monospace"
        _FONTS[key] = pygame.font.SysFont(name, size, bold=bold)
    return _FONTS[key]


_FONTS = {}


def text(surf, s, x, y, size=16, color=TEXT, bold=False, center=False,
         right=False):
    img = font(size, bold).render(str(s), True, color)
    r = img.get_rect()
    if center:
        r.center = (x, y)
    elif right:
        r.midright = (x, y)
    else:
        r.midleft = (x, y)
    surf.blit(img, r)
    return r


def panel(surf, rect, title=None, accent=EDGE):
    pygame.draw.rect(surf, PANEL, rect, border_radius=10)
    pygame.draw.rect(surf, accent, rect, width=1, border_radius=10)
    if title:
        text(surf, title, rect.x + 14, rect.y + 16, 13, MUTED, bold=True)


def gauge(surf, cx, cy, radius, value, vmin, vmax, label, unit,
          major=None, color=CYAN, redline=None, big=True):
    """Analog sweep gauge, 240 degrees, pointing down-left to down-right."""
    # sweep clockwise from lower-left (210) to lower-right (-30) so the
    # dead zone sits at the bottom, like a real cluster
    start, end = 210.0, -30.0
    span = start - end

    frac = 0.0 if vmax <= vmin else (value - vmin) / (vmax - vmin)
    frac = max(0.0, min(1.0, frac))

    # dial face
    pygame.draw.circle(surf, (14, 17, 22), (cx, cy), radius)
    pygame.draw.circle(surf, EDGE, (cx, cy), radius, 2)

    # ticks
    steps = major or 8
    for i in range(steps + 1):
        f = i / steps
        ang = math.radians(start - span * f)
        tcol = RED if (redline is not None and
                       vmin + (vmax - vmin) * f >= redline) else MUTED
        r0 = radius - 16
        r1 = radius - 4
        x0, y0 = cx + r0 * math.cos(ang), cy - r0 * math.sin(ang)
        x1, y1 = cx + r1 * math.cos(ang), cy - r1 * math.sin(ang)
        pygame.draw.line(surf, tcol, (x0, y0), (x1, y1), 3 if i % 2 == 0 else 1)
        if i % 2 == 0:
            rt = radius + 16          # outside the dial -> never collides
            tv = vmin + (vmax - vmin) * f
            text(surf, f"{tv:.0f}", cx + rt * math.cos(ang),
                 cy - rt * math.sin(ang), 13, MUTED, center=True)

    # progress arc
    if frac > 0.001:
        rect = pygame.Rect(cx - radius + 9, cy - radius + 9,
                           (radius - 9) * 2, (radius - 9) * 2)
        arc_col = RED if (redline is not None and value >= redline) else color
        pygame.draw.arc(surf, arc_col, rect,
                        math.radians(start - span * frac),
                        math.radians(start), 6)

    # needle
    ang = math.radians(start - span * frac)
    nl = radius - 22
    tipx, tipy = cx + nl * math.cos(ang), cy - nl * math.sin(ang)
    perp = ang + math.pi / 2
    bw = 5
    b1 = (cx + bw * math.cos(perp), cy - bw * math.sin(perp))
    b2 = (cx - bw * math.cos(perp), cy + bw * math.sin(perp))
    ncol = RED if (redline is not None and value >= redline) else color
    pygame.draw.polygon(surf, ncol, [b1, b2, (tipx, tipy)])
    pygame.draw.circle(surf, (28, 32, 40), (cx, cy), 13)
    pygame.draw.circle(surf, ncol, (cx, cy), 13, 2)

    # readout
    text(surf, f"{value:,.0f}" if big else f"{value:.1f}",
         cx, cy + radius * 0.40, 34 if big else 24, TEXT, bold=True,
         center=True)
    text(surf, unit, cx, cy + radius * 0.40 + 25, 13, MUTED, center=True)
    text(surf, label, cx, cy - radius * 0.46, 14, MUTED, bold=True,
         center=True)


def bar(surf, rect, frac, color=GREEN, warn_below=0.15):
    frac = max(0.0, min(1.0, frac))
    pygame.draw.rect(surf, (14, 17, 22), rect, border_radius=6)
    pygame.draw.rect(surf, EDGE, rect, width=1, border_radius=6)
    if frac > 0:
        w = max(3, int((rect.w - 6) * frac))
        c = RED if frac < warn_below else color
        pygame.draw.rect(surf, c,
                         pygame.Rect(rect.x + 3, rect.y + 3, w, rect.h - 6),
                         border_radius=4)


def arrow(surf, cx, cy, size, left, on):
    col = GREEN if on else DIM
    d = -1 if left else 1
    pts = [(cx + d * size, cy),
           (cx, cy - size), (cx, cy - size * 0.45),
           (cx - d * size, cy - size * 0.45),
           (cx - d * size, cy + size * 0.45),
           (cx, cy + size * 0.45), (cx, cy + size)]
    pygame.draw.polygon(surf, col, pts)


def tell_tale(surf, rect, label, on, color=AMBER):
    col = color if on else DIM
    tcol = (10, 12, 16) if on else MUTED
    pygame.draw.rect(surf, col if on else PANEL, rect, border_radius=7)
    pygame.draw.rect(surf, col, rect, width=1, border_radius=7)
    text(surf, label, rect.centerx, rect.centery, 13, tcol, bold=True,
         center=True)


def car_doors(surf, rect, doors):
    """Top-down car body with four door indicators."""
    body = pygame.Rect(rect.centerx - 34, rect.y + 6, 68, rect.h - 14)
    pygame.draw.rect(surf, (26, 30, 38), body, border_radius=16)
    pygame.draw.rect(surf, EDGE, body, width=1, border_radius=16)
    cab = pygame.Rect(body.x + 11, body.y + 28, body.w - 22, body.h - 58)
    pygame.draw.rect(surf, (16, 19, 25), cab, border_radius=8)

    dw, dh = 13, 24
    ry1 = body.y + int(body.h * 0.30)
    ry2 = body.y + int(body.h * 0.56)
    spots = [(body.x - 5, ry1), (body.right - dw + 5, ry1),
             (body.x - 5, ry2), (body.right - dw + 5, ry2)]
    for i, (x, y) in enumerate(spots):
        r = pygame.Rect(x, y, dw, dh)
        pygame.draw.rect(surf, RED if doors[i] else (40, 46, 56), r,
                         border_radius=4)


class ControlPanel:
    """Small window that drives the simulator - the 'driver's seat'."""

    W, H = 440, 560

    def __init__(self, profile, iface):
        self.prof = profile
        self.iface = iface
        self.screen = pygame.display.set_mode((self.W, self.H))
        pygame.display.set_caption(f"Vehicle Controls - {profile['name']}")

    def draw(self, v, tx, gears):
        s = self.screen
        s.fill(BG)
        text(s, "VEHICLE CONTROLS", 20, 26, 17, CYAN, bold=True)
        text(s, self.prof["name"], 20, 48, 13, MUTED)
        text(s, f"{self.iface}  tx={tx.tx}", 20, 68, 13, MUTED)

        p = pygame.Rect(16, 86, self.W - 32, 150)
        panel(s, p, "STATE")
        text(s, f"{v.speed:6.1f} km/h", 32, 136, 20, TEXT, bold=True)
        text(s, f"{v.rpm:6.0f} rpm", 32, 164, 20, TEXT, bold=True)
        text(s, f"gear {gears[v.gear]}", 32, 192, 20, AMBER, bold=True)
        text(s, f"fuel {v.fuel:.1f}%", 250, 136, 16, MUTED)
        text(s, f"belt {'ON' if v.belt else 'OFF'}", 250, 164, 16,
             GREEN if v.belt else RED)
        text(s, f"noise {'ON' if tx.noise else 'OFF'}", 250, 192, 16,
             AMBER if tx.noise else MUTED)

        p2 = pygame.Rect(16, 248, self.W - 32, 120)
        panel(s, p2, "DOORS / SIGNALS")
        for i, name in enumerate(["FL", "FR", "RL", "RR"]):
            tell_tale(s, pygame.Rect(32 + i * 62, 282, 52, 30), name,
                      v.doors[i], RED)
        arrow(s, 70, 340, 15, True, v.turn_l and v.blink_on)
        arrow(s, self.W - 70, 340, 15, False, v.turn_r and v.blink_on)
        text(s, "BRAKE", self.W // 2, 340, 14,
             RED if v.brake > 0.05 else DIM, bold=True, center=True)

        p3 = pygame.Rect(16, 380, self.W - 32, 164)
        panel(s, p3, "KEYS")
        keys = [
            ("UP / W", "throttle"), ("DOWN / S", "brake"),
            ("LEFT / RIGHT", "turn signals"), ("A / D", "shift down / up"),
            ("1 2 3 4", "doors FL FR RL RR"), ("B / N", "belt / noise"),
            ("ESC / Q", "quit"),
        ]
        for i, (k, d) in enumerate(keys):
            y = 412 + i * 19
            text(s, k, 32, y, 13, CYAN)
            text(s, d, 170, y, 13, MUTED)

        pygame.display.flip()
