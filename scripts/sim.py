#!/usr/bin/env python3
"""
sim.py - the "vehicle". Owns the physics and transmits real CAN frames.

It is the ONLY thing that writes genuine telemetry to the bus. The dashboard
is a passive listener, exactly like a real instrument cluster. That split is
what makes the exercise meaningful: you attack the bus between them.

Controls (focus the Controls window):
    Up / W      throttle
    Down / S    brake
    Left/Right  turn signals
    A / D       shift down / up
    1 2 3 4     toggle doors FL FR RL RR
    B           toggle seatbelt
    N           toggle background noise
    ESC / Q     quit
"""
import argparse
import json
import math
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import can  # noqa: E402
from canframe import encode_signal  # noqa: E402
from bus import open_bus, describe  # noqa: E402
import sigutil  # noqa: E402
from common import load_profile, resolve, list_profiles  # noqa: E402

TICK = 0.02           # 50 Hz physics
GEARS = ["P", "R", "N", "D", "2", "1"]


class Vehicle:
    """Deliberately simple longitudinal model - readable beats accurate."""

    def __init__(self):
        self.speed = 0.0        # km/h
        self.rpm = 800.0
        self.gear = 3           # index into GEARS -> "D"
        self.fuel = 78.0        # %
        self.throttle = 0.0
        self.brake = 0.0
        self.turn_l = False
        self.turn_r = False
        self.doors = [False] * 4
        self.belt = True
        self._blink = 0.0
        self.blink_on = False

    def step(self, dt):
        drive = GEARS[self.gear] in ("D", "2", "1")
        rev = GEARS[self.gear] == "R"

        if drive or rev:
            accel = self.throttle * 42.0 - self.brake * 70.0
        else:
            accel = -self.brake * 70.0
        accel -= 3.2 + self.speed * 0.055          # drag + rolling resistance

        if self.speed <= 0 and accel < 0 and not self.throttle:
            accel = 0.0
        self.speed = max(0.0, min(255.0, self.speed + accel * dt))

        # engine speed from road speed, plus idle
        ratio = {"D": 42.0, "2": 70.0, "1": 95.0, "R": 80.0}.get(
            GEARS[self.gear], 0.0)
        target = 800.0 + self.speed * ratio + self.throttle * 900.0
        if not (drive or rev):
            target = 800.0 + self.throttle * 3200.0
        self.rpm += (min(target, 7000.0) - self.rpm) * min(1.0, dt * 4.0)

        self.fuel = max(0.0, self.fuel - (0.00018 + self.throttle * 0.0016) * dt * 60)

        self._blink += dt
        if self._blink >= 0.4:
            self._blink = 0.0
            self.blink_on = not self.blink_on
        if not (self.turn_l or self.turn_r):
            self.blink_on = False


class Transmitter:
    """Maps vehicle state onto the selected car's real CAN IDs."""

    def __init__(self, bus, profile, noise=True):
        self.bus = bus
        self.prof = profile
        self.ch = profile["channels"]
        self.lamps = profile.get("lamps", {})
        self.noise = noise
        self.tx = 0
        self._next = {}
        self._noise_ids = self._pick_noise_ids()

    def _pick_noise_ids(self):
        """Real IDs from the same DBC that we never use for the dashboard,
        so background chatter looks native to this vehicle."""
        used = {m["frame_id"] for m in self.ch.values()}
        pool = [i for i in self.prof.get("noise_ids", []) if i not in used]
        return pool[:40]

    def _frame(self, chan, value):
        m = self.ch.get(chan)
        if not m:
            return None
        data = bytearray(m["dlc"])
        encode_signal(data, m, value)
        return m, data

    def _group(self, items):
        """Combine channels that live in the same CAN message into one frame
        (a real cluster gets door states packed together, not one per frame)."""
        frames = {}
        for chan, value in items:
            m = self.ch.get(chan)
            if not m:
                continue
            key = (m["frame_id"], m["is_extended"], m["dlc"])
            buf = frames.setdefault(key, bytearray(m["dlc"]))
            encode_signal(buf, m, value)
        return frames

    def send(self, v, now):
        items = [
            ("speed", v.speed / self.ch.get("speed", {}).get("to_kmh", 1.0)),
            ("rpm", v.rpm),
            ("gear", self._gear_value(v)),
            ("fuel", self._scaled("fuel", v.fuel)),
            ("brake", 1 if v.brake > 0.05 else 0),
            ("seatbelt", self._belt_value(v)),
            ("turn_left", 1 if (v.turn_l and v.blink_on) else 0),
            ("turn_right", 1 if (v.turn_r and v.blink_on) else 0),
            ("doors", self._door_value(v)),
            ("door_fl", 1 if v.doors[0] else 0),
            ("door_fr", 1 if v.doors[1] else 0),
            ("door_rl", 1 if v.doors[2] else 0),
            ("door_rr", 1 if v.doors[3] else 0),
        ]
        frames = self._group(items)

        # transmit every warning lamp as OFF. The cluster only lights one when
        # somebody injects a frame setting that bit - which is the whole point.
        for name, m in self.lamps.items():
            key = (m["frame_id"], m["is_extended"], m["dlc"])
            buf = frames.setdefault(key, bytearray(m["dlc"]))
            encode_signal(buf, m, 0)

        for key, data in frames.items():
            fid, ext, dlc = key
            self._emit(fid, ext, bytes(data))

        if self.noise and self._noise_ids:
            for fid in random.sample(self._noise_ids,
                                     min(3, len(self._noise_ids))):
                self._emit(fid, False,
                           bytes(random.getrandbits(8) for _ in range(8)))

    def _emit(self, fid, ext, data):
        try:
            self.bus.send(can.Message(arbitration_id=fid,
                                      is_extended_id=bool(ext),
                                      data=data))
            self.tx += 1
        except can.CanError:
            pass

    # --- value mapping helpers -------------------------------------------
    def _scaled(self, chan, pct):
        m = self.ch.get(chan)
        if not m:
            return 0
        return m["min"] + (m["max"] - m["min"]) * (pct / 100.0)

    def _gear_value(self, v):
        m = self.ch.get("gear")
        if not m:
            return 0
        # map P R N D 2 1 into whatever range this signal supports
        return min(m["max"], max(m["min"], m["min"] + v.gear))

    def _door_value(self, v):
        m = self.ch.get("doors")
        if not m:
            return 0
        if m["length"] >= 4:
            return sum(1 << i for i, d in enumerate(v.doors) if d)
        return 1 if any(v.doors) else 0

    def _belt_value(self, v):
        # signal usually means "unbuckled warning" - invert
        return 0 if v.belt else 1


def build_arg_parser():
    ap = argparse.ArgumentParser(
        description="ICSIM-style CAN vehicle simulator driven by real opendbc data")
    ap.add_argument("-i", "--interface", default="vcan0")
    ap.add_argument("-c", "--car", default="toyota_prius_2010_pt",
                    help="profile name or substring, e.g. 'prius'")
    ap.add_argument("--no-noise", action="store_true",
                    help="disable background CAN chatter (easy mode)")
    ap.add_argument("--list", action="store_true", help="list car profiles")
    ap.add_argument("--headless", type=float, default=0.0,
                    help="run N seconds with a scripted drive, no window")
    return ap


def main():
    sigutil.install()
    args = build_arg_parser().parse_args()
    if args.list:
        for p in list_profiles():
            print(f"{p['score']:2}  {p['name']:44} {','.join(p['coverage'])}")
        return

    prof = load_profile(resolve(args.car))
    bus = open_bus(args.interface)
    tx = Transmitter(bus, prof, noise=not args.no_noise)
    v = Vehicle()

    print(f"[+] car      : {prof['name']}")
    print(f"[+] interface: {args.interface}")
    print(f"[+] channels : {', '.join(sorted(prof['channels']))}")
    for ch, m in sorted(prof["channels"].items()):
        print(f"      {ch:11} id=0x{m['frame_id']:03X} {m['message']}.{m['signal']}")

    try:
        if args.headless:
            run_headless(v, tx, args.headless)
        else:
            run_gui(v, tx, args, prof)
    except KeyboardInterrupt:
        print("\n[+] stopped")
    finally:
        bus.shutdown()


def run_headless(v, tx, seconds):
    """Scripted drive used by verify.sh - no display needed."""
    print(f"[+] headless drive for {seconds}s")
    t0 = last = time.time()
    while time.time() - t0 < seconds:
        now = time.time()
        dt = now - last
        if dt < TICK:
            time.sleep(TICK - dt)
            continue
        last = now
        el = now - t0
        v.throttle = 0.8 if el < seconds * 0.6 else 0.0
        v.brake = 0.0 if el < seconds * 0.6 else 0.6
        v.turn_l = el % 4 < 2
        v.turn_r = not v.turn_l
        v.doors[0] = el % 6 > 3
        v.step(dt)
        tx.send(v, now)
    print(f"[+] sent {tx.tx} frames | final speed={v.speed:.1f} rpm={v.rpm:.0f}")


def run_gui(v, tx, args, prof):
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    import pygame
    from ui import ControlPanel

    pygame.init()
    panel = ControlPanel(prof, args.interface)
    clock = pygame.time.Clock()
    last = time.time()
    running = True
    while running:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            elif ev.type == pygame.KEYDOWN:
                if ev.key in (pygame.K_ESCAPE, pygame.K_q):
                    running = False
                elif ev.key == pygame.K_LEFT:
                    v.turn_l, v.turn_r = not v.turn_l, False
                elif ev.key == pygame.K_RIGHT:
                    v.turn_r, v.turn_l = not v.turn_r, False
                elif ev.key == pygame.K_d:
                    v.gear = min(len(GEARS) - 1, v.gear + 1)
                elif ev.key == pygame.K_a:
                    v.gear = max(0, v.gear - 1)
                elif ev.key == pygame.K_b:
                    v.belt = not v.belt
                elif ev.key == pygame.K_n:
                    tx.noise = not tx.noise
                elif pygame.K_1 <= ev.key <= pygame.K_4:
                    i = ev.key - pygame.K_1
                    v.doors[i] = not v.doors[i]

        keys = pygame.key.get_pressed()
        v.throttle = 1.0 if (keys[pygame.K_UP] or keys[pygame.K_w]) else 0.0
        v.brake = 1.0 if (keys[pygame.K_DOWN] or keys[pygame.K_s]) else 0.0

        now = time.time()
        dt = min(0.1, now - last)
        last = now
        v.step(dt)
        tx.send(v, now)
        panel.draw(v, tx, GEARS)
        clock.tick(50)
    pygame.quit()


if __name__ == "__main__":
    main()
