#!/usr/bin/env python3
"""Contact sheet of every tell-tale icon, lit and unlit."""
import os, sys
os.environ["SDL_VIDEODRIVER"] = "dummy"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pygame
from icons import ICONS, draw_icon

pygame.init()
names = ["ABS","AIRBAG","ESP/TCS","CHECK ENG","BATT","OIL","COOLANT",
         "TPMS","BRAKE!","BELT","DOOR","FUEL LOW","HIGH BEAM"]
CW, CH = 150, 150
cols = 7
rows = (len(names)+cols-1)//cols * 2
W, H = cols*CW, rows*CH//2*2 + 40
surf = pygame.display.set_mode((W, H))
surf.fill((10,12,16))
f = pygame.font.SysFont("dejavusansmono", 12)
AMBER=(248,176,56); DIM=(44,50,62)
for i, n in enumerate(names):
    c, r = i % cols, i // cols
    cx = c*CW + CW//2
    cy = r*CH*2 + 70
    draw_icon(surf, n, cx, cy, 34, AMBER)
    draw_icon(surf, n, cx, cy + CH, 34, DIM)
    img = f.render(n, True, (150,160,175))
    surf.blit(img, img.get_rect(center=(cx, cy+46)))
pygame.image.save(surf, sys.argv[1] if len(sys.argv)>1 else "/tmp/icons.png")
print("saved")
