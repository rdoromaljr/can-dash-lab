#!/usr/bin/env python3
"""Offscreen render of the control panel."""
import os, sys
os.environ["SDL_VIDEODRIVER"] = "dummy"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pygame
from common import load_profile, resolve
from ui import ControlPanel
from sim import Vehicle, GEARS

out = sys.argv[2] if len(sys.argv) > 2 else "/tmp/panel.png"
pygame.init()
prof = load_profile(resolve(sys.argv[1] if len(sys.argv) > 1 else "prius"))
p = ControlPanel(prof, "vcan0")
v = Vehicle(); v.speed = 118.4; v.rpm = 4250; v.fuel = 62
v.doors = [True, False, False, True]; v.turn_l = True; v.blink_on = True
v.brake = 1.0; v.belt = False


class T:
    tx = 18422
    noise = True


p.draw(v, T(), GEARS)
pygame.image.save(p.screen, out)
print("saved", out, os.path.getsize(out), "bytes")
