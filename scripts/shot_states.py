#!/usr/bin/env python3
"""Render the cluster in several states to catch layout collisions."""
import os, sys, time, collections
os.environ["SDL_VIDEODRIVER"] = "dummy"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pygame
from common import load_profile, resolve
import dash as D

car = sys.argv[1] if len(sys.argv) > 1 else "prius"
out = sys.argv[2] if len(sys.argv) > 2 else "/tmp/states.png"
pygame.init()
prof = load_profile(resolve(car))

STATES = [
    ("idle, all lamps off", dict(speed=0, rpm=800, gear="P", fuel=78,
                                 doors=[False]*4, lamps=False, anom=False)),
    ("redline, ALL lamps lit", dict(speed=185, rpm=7800, gear="1", fuel=4,
                                    doors=[True]*4, lamps=True, anom=True)),
    ("cruise, some lamps", dict(speed=97, rpm=3100, gear="D", fuel=46,
                                doors=[False,True,False,False],
                                lamps="some", anom=True)),
]
shots = []
for title, st in STATES:
    c = D.Cluster(prof, "vcan0")
    c.speed, c.rpm, c.gear, c.fuel = st["speed"], st["rpm"], st["gear"], st["fuel"]
    c.doors = st["doors"]
    c.brake = st["rpm"] > 5000
    c.belt_warn = st["fuel"] < 10
    c.turn_l = st["speed"] > 50
    c.frames, c.fps_bus, c.last_rx = 18422, 412, time.time()
    names = list(c.lamps)
    if st["lamps"] is True:
        for n in names: c.lamp_on[n] = True
    elif st["lamps"] == "some":
        for n in names[:3]: c.lamp_on[n] = True
    for i, fid in enumerate([0x0B4,0x1C4,0x127,0x620,0x226,0x2C4,0x3B7,
                             0x4C1,0x5A1,0x610]):
        c.ids[fid] = 900 - i*37; c.last_seen[fid] = time.time()
    if st["anom"]:
        c.fuzz_hits, c.glitches = 1340, 7
        c.anomalies = collections.deque([
            (time.time()-0.2, 0x666, "deadbeefdeadbeef"),
            (time.time()-1.1, 0x7a1, "ff00ff00ff00ff00"),
        ])
        c.anomaly_ids = {0x666: time.time()}
    s = pygame.Surface((D.W, D.H))
    screen = pygame.display.set_mode((D.W, D.H))
    D.draw(screen, c)
    s.blit(screen, (0, 0))
    shots.append((title, s))

sheet = pygame.Surface((D.W, D.H * len(shots)))
f = pygame.font.SysFont("dejavusansmono", 15, bold=True)
for i, (title, s) in enumerate(shots):
    sheet.blit(s, (0, i * D.H))
    img = f.render(title, True, (255, 230, 120))
    sheet.blit(img, (24, i * D.H + D.H - 22))
pygame.image.save(sheet, out)
print("saved", out)
