#!/usr/bin/env python3
"""Offscreen render of the cluster for docs/testing. No display needed."""
import os, sys, time
os.environ["SDL_VIDEODRIVER"] = "dummy"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pygame
from common import load_profile, resolve
import dash as D

car = sys.argv[1] if len(sys.argv) > 1 else "prius"
out = sys.argv[2] if len(sys.argv) > 2 else "/tmp/cluster.png"
pygame.init()
prof = load_profile(resolve(car))
c = D.Cluster(prof, "vcan0")
c.speed = 118.4; c.rpm = 4250; c.gear = "D"; c.fuel = 62
c.doors = [True, False, False, True]
c.turn_l = True; c.brake = True; c.belt_warn = True
c.frames = 18422; c.fps_bus = 412; c.last_rx = time.time()
# simulate a live injection so the new panels render
for name in list(c.lamps)[:3]:
    c.lamp_on[name] = True
c.fuzz_hits = 1340; c.glitches = 7
import collections
c.anomalies = collections.deque([
    (time.time() - 0.2, 0x666, "deadbeefdeadbeef"),
    (time.time() - 0.9, 0x7a1, "ff00ff00ff00ff00"),
    (time.time() - 1.8, 0x0f3, "a1b2c3d4e5f60708"),
    (time.time() - 3.4, 0x512, "0011223344556677"),
])
c.anomaly_ids = {0x666: time.time(), 0x7a1: time.time()}
for i, fid in enumerate([0x0B4,0x1C4,0x127,0x620,0x226,0x2C4,0x3B7,0x4C1,
                         0x5A1,0x610,0x611,0x612]):
    c.ids[fid] = 900 - i*37; c.last_seen[fid] = time.time()
screen = pygame.display.set_mode((D.W, D.H))
D.draw(screen, c)
pygame.image.save(screen, out)
print("saved", out, os.path.getsize(out), "bytes")
