#!/usr/bin/env python3
"""
dash.py - the instrument cluster.

This process NEVER talks to the simulator. It only listens to CAN frames and
decodes them using the selected car's DBC layout. That is the whole point:
if you inject a frame with the right ID and bit layout, the cluster believes
you - there is no authentication on CAN.

Run:
    ./dash.py -i vcan0 -c prius
"""
import argparse
import os
import sys
import time
from collections import deque

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import can  # noqa: E402
from canframe import decode_signal  # noqa: E402
from bus import open_bus, describe  # noqa: E402
import sigutil  # noqa: E402
from common import load_profile, resolve  # noqa: E402
import ui  # noqa: E402
from ui import (BG, PANEL, EDGE, TEXT, MUTED, CYAN, GREEN, AMBER, RED, DIM,
                text, panel, gauge, bar, arrow, tell_tale, car_doors)  # noqa
from cluster import (vignette, binnacle, dial, dial_lamps, strip_lamps,
                     bar_gauge, seg_bar, FACE_EDGE)  # noqa: E402
from cluster import (BG as BG_D, TXT as TXT_D, MUTED as MUTED_D,
                     DIM as DIM_D, CYAN as CYAN_D, GREEN as GREEN_D,
                     AMBER as AMBER_D, RED as RED_D)  # noqa: E402
from icons import icon_arrow  # noqa: E402

W, H = 1180, 680
GEARS = ["P", "R", "N", "D", "2", "1"]


class Cluster:
    def __init__(self, prof, iface, show_ids=True):
        self.prof = prof
        self.ch = prof["channels"]
        self.iface = iface
        self.show_ids = show_ids

        # decoded state
        self.speed = 0.0
        self.rpm = 0.0
        self.gear = "-"
        self.fuel = 0.0
        self.doors = [False] * 4
        self.turn_l = False
        self.turn_r = False
        self.brake = False
        self.belt_warn = False

        # bus stats
        self.frames = 0
        self.ids = {}
        self.last_seen = {}
        self._win = deque()
        self.fps_bus = 0.0
        self.last_rx = 0.0

        self._per_door = any(k in self.ch for k in
                             ("door_fl", "door_fr", "door_rl", "door_rr"))

        # warning lamps mined from this car's DBC (or synthesized)
        self.lamps = prof.get("lamps", {})
        self.lamp_on = {k: False for k in self.lamps}
        self.lamp_until = {k: 0.0 for k in self.lamps}
        self.lamp_ever = set()

        # anomaly feed - anything the real ECUs never send
        self.known_ids = set()
        # every ID this car legitimately uses (dash + lamps + background noise)
        self.native_ids = {m["frame_id"] for m in self.ch.values()}
        self.native_ids |= {m["frame_id"] for m in prof.get("lamps", {}).values()}
        self.native_ids |= set(prof.get("noise_ids", []))
        self.anomalies = deque(maxlen=6)
        self.anomaly_ids = {}
        self.fuzz_hits = 0
        self.glitches = 0
        self.glitch_until = {}
        self.glitch_val = {}
        self.true_val = {}
        self.learning_until = time.time() + 3.0

        # reverse map: frame_id -> [(channel, meta)]
        self.by_id = {}
        for name, m in self.ch.items():
            self.by_id.setdefault(m["frame_id"], []).append((name, m))
        for name, m in self.lamps.items():
            self.by_id.setdefault(m["frame_id"], []).append(("lamp:" + name, m))

    def on_frame(self, msg):
        now = time.time()
        self.frames += 1
        self.last_rx = now
        self.ids[msg.arbitration_id] = self.ids.get(msg.arbitration_id, 0) + 1
        self.last_seen[msg.arbitration_id] = now
        self._win.append(now)
        while self._win and now - self._win[0] > 1.0:
            self._win.popleft()
        self.fps_bus = len(self._win)

        # Anything whose ID does not belong to this vehicle's own database is
        # an injection. Learning by observation alone is unreliable because the
        # sim emits only a few random noise IDs per tick.
        if now < self.learning_until:
            self.known_ids.add(msg.arbitration_id)
        if msg.arbitration_id not in self.native_ids:
            self.fuzz_hits += 1
            self.anomaly_ids[msg.arbitration_id] = now
            self.anomalies.appendleft(
                (now, msg.arbitration_id, msg.data.hex()))

        for chan, m in self.by_id.get(msg.arbitration_id, []):
            if len(msg.data) < m["dlc"]:
                continue
            val = decode_signal(bytes(msg.data), m)
            self._apply(chan, val, m)

    def _latch(self, key, v, jump):
        """Hold an implausible (injected) value briefly so it is visible.

        Compare against the last *genuine* value, never the latched one, or a
        single injection re-triggers on every subsequent real frame.
        """
        now = time.time()
        prev = self.true_val.get(key)
        self.true_val[key] = v
        if prev is not None and abs(v - prev) > jump:
            self.glitch_until[key] = now + 1.2
            self.glitch_val[key] = v
            self.glitches += 1
        if now < self.glitch_until.get(key, 0.0):
            return self.glitch_val[key]
        return v

    def _apply(self, chan, val, m):
        if chan.startswith("lamp:"):
            name = chan[5:]
            if int(val):
                # latch for 1.5s - a single fuzzed frame must be visible
                self.lamp_until[name] = time.time() + 1.5
                self.lamp_ever.add(name)
            self.lamp_on[name] = time.time() < self.lamp_until[name]
            return
        if chan == "speed":
            # normalise the DBC's native unit (mph/m-s) into km/h
            v = max(0.0, val * m.get("to_kmh", 1.0))
            self.speed = self._latch("speed", v, 25.0)
        elif chan == "rpm":
            self.rpm = self._latch("rpm", max(0.0, val), 1500.0)
        elif chan == "fuel":
            span = (m["max"] - m["min"]) or 1.0
            self.fuel = max(0.0, min(100.0, (val - m["min"]) / span * 100.0))
        elif chan == "gear":
            idx = int(round(val - m["min"]))
            self.gear = GEARS[idx] if 0 <= idx < len(GEARS) else str(int(val))
        elif chan in ("door_fl", "door_fr", "door_rl", "door_rr"):
            self.doors[["door_fl", "door_fr", "door_rl",
                        "door_rr"].index(chan)] = bool(int(val))
        elif chan == "doors":
            iv = int(val)
            if m["length"] >= 4:
                self.doors = [bool(iv >> i & 1) for i in range(4)]
            elif not self._per_door:
                self.doors = [bool(iv)] * 4
        elif chan == "turn_left":
            self.turn_l = bool(int(val))
        elif chan == "turn_right":
            self.turn_r = bool(int(val))
        elif chan == "brake":
            self.brake = bool(int(val))
        elif chan == "seatbelt":
            self.belt_warn = bool(int(val))


def draw(screen, c):
    import pygame
    screen.fill(BG_D)
    now = time.time()

    # ================= binnacle =================
    outer = pygame.Rect(16, 10, W - 32, 500)
    binn = binnacle(screen, outer)

    # ---- header line inside the bezel ----
    stale = (now - c.last_rx) > 1.0 if c.last_rx else True
    text(screen, c.prof["name"].replace("_", " ").upper(),
         binn.x + 26, binn.y + 26, 13, MUTED_D, bold=True)
    text(screen, c.iface, binn.right - 26, binn.y + 26, 12, MUTED_D,
         right=True)
    sc = RED_D if stale else GREEN_D
    pygame.draw.circle(screen, sc, (binn.right - 112, binn.y + 26), 4)
    text(screen, "NO SIGNAL" if stale else "LIVE",
         binn.right - 102, binn.y + 26, 12, sc, bold=True)

    # ---- lamp colour map ----
    lamp_cols = {"ABS": AMBER_D, "AIRBAG": RED_D, "ESP/TCS": AMBER_D,
                 "CHECK ENG": AMBER_D, "BATT": RED_D, "OIL": RED_D,
                 "COOLANT": RED_D, "TPMS": AMBER_D, "BRAKE!": RED_D,
                 "FUEL LOW": AMBER_D}

    # ---- turn signals sit high, flanking the trip computer ----
    for left, on in ((True, c.turn_l), (False, c.turn_r)):
        ax = binn.centerx - 150 if left else binn.centerx + 150
        icon_arrow(screen, ax, binn.y + 58, 17,
                   GREEN_D if on else DIM_D, left=left)

    # ================= dials =================
    cy = binn.y + 252
    r = 142
    lx = binn.x + 214
    rx = binn.right - 214

    # tachometer (left) - clock in the face, like a real cluster
    dial(screen, lx, cy, r, min(c.rpm, 8000), 0, 8000, 8,
         "", "rpm", redline=6000, accent=AMBER_D)

    # speedometer (right)
    _sp = c.ch.get("speed", {})
    sp_max = _sp.get("max", 240.0) * _sp.get("to_kmh", 1.0)
    import math as _m
    sp_max = max(120.0, min(280.0, sp_max))
    sp_max = _m.ceil(sp_max / 20.0) * 20
    # speedometer (right) - odometer in the face
    dial(screen, rx, cy, r, min(c.speed, sp_max), 0, sp_max, 8,
         "", "km/h", accent=CYAN_D)

    # ---- warning symbols INSIDE the dial faces ----
    # engine-related lamps live in the tacho, chassis lamps in the speedo,
    # exactly how a real cluster groups them.
    TACH_SET = ("CHECK ENG", "OIL", "COOLANT", "BATT")
    SPEED_SET = ("ABS", "ESP/TCS", "TPMS", "BRAKE!")
    in_tach, in_speed, leftover = [], [], []
    for name in c.lamps:
        item = (name, c.lamp_on.get(name, False),
                lamp_cols.get(name, AMBER_D))
        if name in TACH_SET:
            in_tach.append(item)
        elif name in SPEED_SET:
            in_speed.append(item)
        else:
            leftover.append(item)
    dial_lamps(screen, lx, cy, r, in_tach[:4])
    dial_lamps(screen, rx, cy, r, in_speed[:4])

    # ================= centre trip computer =================
    ip = pygame.Rect(binn.centerx - 100, cy - 118, 200, 206)
    pygame.draw.rect(screen, (11, 13, 17), ip, border_radius=10)
    pygame.draw.rect(screen, (44, 50, 62), ip, width=1, border_radius=10)

    # gear selector, PRND style
    gears = ["P", "R", "N", "D", "2", "1"]
    gy = ip.y + 34
    text(screen, "GEAR", ip.centerx, ip.y + 16, 11, MUTED_D, bold=True,
         center=True)
    gw = ip.w / len(gears)
    for i, g in enumerate(gears):
        on = (g == c.gear)
        gx = ip.x + gw * (i + 0.5)
        text(screen, g, gx, gy, 20 if on else 15,
             GREEN_D if on else DIM_D, bold=True, center=True)
        if on:
            pygame.draw.line(screen, GREEN_D, (gx - 9, gy + 15),
                             (gx + 9, gy + 15), 2)

    # big speed repeat (digital), like a modern cluster
    text(screen, f"{c.speed:,.0f}", ip.centerx, gy + 52, 42, TXT_D,
         bold=True, center=True)
    text(screen, "km/h", ip.centerx, gy + 80, 11, MUTED_D, center=True)

    # door pips - compact, always aligned
    for i in range(4):
        px = ip.centerx - 33 + i * 22
        py = ip.bottom - 76
        col = RED_D if c.doors[i] else (40, 46, 58)
        pygame.draw.rect(screen, col, pygame.Rect(px - 7, py - 5, 14, 10),
                         border_radius=2)
    text(screen, "DOORS", ip.centerx, ip.bottom - 90, 9, DIM_D, bold=True,
         center=True)

    odo = int(c.frames / 50.0)
    pygame.draw.line(screen, (36, 41, 52), (ip.x + 16, ip.bottom - 62),
                     (ip.right - 16, ip.bottom - 62), 1)
    text(screen, time.strftime("%H:%M"), ip.centerx, ip.bottom - 48, 15,
         (170, 180, 196), bold=True, center=True)
    text(screen, f"{odo:06d} km", ip.centerx, ip.bottom - 28, 12,
         MUTED_D, center=True)
    text(screen, f"{len(c.ids)} IDs  {c.fps_bus:.0f} fps",
         ip.centerx, ip.bottom - 12, 10, DIM_D, center=True)

    # ================= bottom status bar (Librow layout) =================
    sb = pygame.Rect(binn.x + 26, binn.bottom - 76, binn.w - 52, 46)
    pygame.draw.rect(screen, (10, 12, 16), sb, border_radius=8)
    pygame.draw.rect(screen, (38, 43, 54), sb, width=1, border_radius=8)

    # fuel bar, left end
    fuel_r = pygame.Rect(sb.x + 34, sb.y + 12, 150, 14)
    seg_bar(screen, fuel_r, c.fuel / 100.0, "FUEL LOW", col=GREEN_D,
            left_label="E", mid_label="1/2", right_label="F")

    # engine temperature, right end (synthesised from rpm - no DBC signal)
    temp_f = max(0.0, min(1.0, 0.25 + (c.rpm / 8000.0) * 0.6))
    temp_r = pygame.Rect(sb.right - 184, sb.y + 12, 150, 14)
    seg_bar(screen, temp_r, temp_f, "COOLANT", col=CYAN_D, warn=-1.0,
            left_label="40", mid_label="80", right_label="120", flip=False)

    # tell-tale symbols centred between the two bars
    strip_items = [("BELT", c.belt_warn, RED_D),
                   ("DOOR", any(c.doors), AMBER_D),
                   ("BRAKE", c.brake, RED_D)] + leftover
    strip = pygame.Rect(fuel_r.right + 40, sb.y + 5,
                        (temp_r.x - 40) - (fuel_r.right + 40), 36)
    strip_lamps(screen, strip, strip_items[:7], bg=(10, 12, 16))



    # ================= attack / bus panel =================
    ap_ = pygame.Rect(16, 516, W - 32, 148)
    attack_live = c.anomalies and (now - c.anomalies[0][0]) < 2.0
    pygame.draw.rect(screen, (13, 15, 20), ap_, border_radius=14)
    pygame.draw.rect(screen, RED_D if attack_live else (46, 52, 64), ap_,
                     width=2 if attack_live else 1, border_radius=14)

    text(screen, "INJECTION DETECTED" if attack_live else "BUS MONITOR",
         ap_.x + 20, ap_.y + 20, 14, RED_D if attack_live else MUTED_D,
         bold=True)
    text(screen, f"rogue {c.fuzz_hits}   glitches {c.glitches}",
         ap_.right - 20, ap_.y + 20, 12,
         RED_D if c.fuzz_hits else MUTED_D, right=True)

    # top talkers, left half
    mapped = {m["frame_id"] for m in c.ch.values()}
    mapped |= {m["frame_id"] for m in c.lamps.values()}
    top = sorted(c.ids.items(), key=lambda kv: -kv[1])[:10]
    for i, (fid, n) in enumerate(top):
        col, row = i % 5, i // 5
        x = ap_.x + 20 + col * 112
        y = ap_.y + 56 + row * 26
        rogue = fid in c.anomaly_ids
        fc = RED_D if rogue else (CYAN_D if fid in mapped else MUTED_D)
        text(screen, f"0x{fid:03X}", x, y, 14, fc,
             bold=fid in mapped or rogue)
        text(screen, str(n), x + 62, y, 11, DIM_D)

    # injection feed, right half
    fx = ap_.x + 612
    pygame.draw.line(screen, (40, 46, 58), (fx - 18, ap_.y + 44),
                     (fx - 18, ap_.bottom - 16), 1)
    if not c.anomalies:
        text(screen, "no foreign IDs seen", fx, ap_.y + 60, 12, DIM_D)
        text(screen, "caringcaribou -i vcan0 fuzzer brute 0x%03X .."
             % (list(c.lamps.values())[0]["frame_id"] if c.lamps else 0),
             fx, ap_.y + 82, 11, DIM_D)
    else:
        for i, (t, fid, data) in enumerate(list(c.anomalies)[:4]):
            y = ap_.y + 56 + i * 22
            age = now - t
            col = RED_D if age < 1.0 else (AMBER_D if age < 3.0 else DIM_D)
            text(screen, f"0x{fid:03X}", fx, y, 13, col, bold=True)
            text(screen, data[:16], fx + 62, y, 11, MUTED_D)

    pygame.display.flip()

def main():
    ap = argparse.ArgumentParser(description="CAN instrument cluster (listener)")
    ap.add_argument("-i", "--interface", default="vcan0")
    ap.add_argument("-c", "--car", default="toyota_prius_2010_pt")
    ap.add_argument("--headless", type=float, default=0.0,
                    help="listen N seconds and print decoded state, no window")
    args = ap.parse_args()
    sigutil.install()

    prof = load_profile(resolve(args.car))
    c = Cluster(prof, args.interface)
    bus = open_bus(args.interface)

    print(f"[+] cluster listening on {args.interface} as {prof['name']}")
    for ch, m in sorted(prof["channels"].items()):
        print(f"      {ch:11} id=0x{m['frame_id']:03X} "
              f"bits {m['start_bit']}+{m['length']} "
              f"{m['byte_order'][:6]} -> {m['message']}.{m['signal']}")

    if args.headless:
        try:
            t0 = time.time()
            while time.time() - t0 < args.headless:
                msg = bus.recv(timeout=0.2)
                if msg:
                    c.on_frame(msg)
            print(f"\n[+] frames={c.frames} unique_ids={len(c.ids)}")
            print(f"    speed={c.speed:.1f} rpm={c.rpm:.0f} gear={c.gear} "
                  f"fuel={c.fuel:.0f}% doors={c.doors}")
            print(f"    turn L/R={c.turn_l}/{c.turn_r} brake={c.brake} "
                  f"belt_warn={c.belt_warn}")
            lit = [k for k, v in c.lamp_on.items() if v]
            print(f"    LAMPS_EVER_LIT={sorted(c.lamp_ever)} LIT_NOW={lit}")
            print(f"    ROGUE_FRAMES={c.fuzz_hits} GLITCHES={c.glitches} "
                  f"ROGUE_IDS={len(c.anomaly_ids)}")
        except KeyboardInterrupt:
            print("\n[+] stopped")
        finally:
            bus.shutdown()
        return

    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    import pygame
    pygame.init()
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption(f"Instrument Cluster - {prof['name']}")
    clock = pygame.time.Clock()

    running = True
    try:
        while running:
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    running = False
                elif ev.type == pygame.KEYDOWN and ev.key in (
                        pygame.K_ESCAPE, pygame.K_q):
                    running = False
            # drain everything queued since last frame
            for _ in range(600):
                msg = bus.recv(timeout=0.0)
                if msg is None:
                    break
                c.on_frame(msg)
            draw(screen, c)
            clock.tick(40)
    except KeyboardInterrupt:
        print("\n[+] stopped")
    finally:
        pygame.quit()
        bus.shutdown()


if __name__ == "__main__":
    main()
