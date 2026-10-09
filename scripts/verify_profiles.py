#!/usr/bin/env python3
"""Round-trip check: encode a value into a frame, decode it back."""
import json, os, glob, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from canframe import encode_signal, decode_signal

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
bad = tot = 0
for p in sorted(glob.glob(os.path.join(ROOT, "profiles", "*.json"))):
    if os.path.basename(p).startswith("_"): continue
    prof = json.load(open(p))
    for ch, m in prof["channels"].items():
        lo, hi = m["min"], m["max"]
        for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
            want = lo + (hi - lo) * frac
            data = bytearray(m["dlc"])
            encode_signal(data, m, want)
            got = decode_signal(bytes(data), m)
            tol = abs(m["scale"]) * 1.001 + 1e-6
            tot += 1
            if abs(got - want) > tol:
                bad += 1
                if bad <= 8:
                    print(f"MISMATCH {prof['name']}.{ch} ({m['signal']}) "
                          f"want={want:.3f} got={got:.3f} scale={m['scale']}")
print(f"\nround-trip: {tot-bad}/{tot} ok, {bad} mismatches")
sys.exit(1 if bad else 0)
