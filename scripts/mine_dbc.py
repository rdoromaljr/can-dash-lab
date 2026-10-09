#!/usr/bin/env python3
"""
mine_dbc.py - scan opendbc DBC files and build dashboard profiles.

For each DBC we try to bind 7 "dashboard channels" to a real
(message, signal) pair from that vehicle's database:

    speed, rpm, gear, fuel, doors, turn_left, turn_right, brake, seatbelt

Output: profiles/<name>.json  used by the simulator + dashboard.
"""
import json
import os
import re
import sys
import glob

import cantools

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DBC_DIR = os.path.join(ROOT, "dbc")
PROF_DIR = os.path.join(ROOT, "profiles")

# channel -> (list of regex patterns on signal name, required unit hint or None)
# Patterns are ordered: earlier = higher confidence.
CHANNELS = {
    "speed": [
        r"^VEHICLE_SPEED$", r"^SPEED$", r"^VehicleSpeed", r"^VEH_SPEED",
        r"^Vehicle_Speed", r"WHEEL_SPEED_FR", r"WheelSpeed_FR",
        r"SPEED.*KPH", r"^ESP_VSS", r"VehSpd", r"VSS",
        r"SPEED$", r"Speed$",
    ],
    "rpm": [
        r"^ENGINE_RPM$", r"^RPM$", r"EngineRPM", r"ENGINE_SPEED",
        r"Engine_RPM", r"EngSpd", r"MOTOR_RPM", r"RPM$",
    ],
    "gear": [
        r"^GEAR$", r"GEAR_SHIFTER", r"^CUR_GEAR", r"CURRENT_GEAR",
        r"GearShifter", r"TRANS_GEAR", r"GEAR$",
    ],
    "fuel": [
        r"FUEL_LEVEL", r"FuelLevel", r"FUEL_GAUGE", r"FUEL$", r"FUEL",
    ],
    "doors": [
        r"DOOR_OPEN(?!_[FR])", r"DOOR_AJAR(?!_[FR])", r"DOORS?$",
        r"DOOR_STATUS", r"DOOR",
    ],
    "door_fl": [r"DOOR_OPEN_FL", r"DOOR_AJAR_FL", r"DoorOpen_?FL",
                r"DRIVER_DOOR", r"DOOR.*_FL\b", r"FL_DOOR"],
    "door_fr": [r"DOOR_OPEN_FR", r"DOOR_AJAR_FR", r"DoorOpen_?FR",
                r"PASSENGER_DOOR", r"DOOR.*_FR\b", r"FR_DOOR"],
    "door_rl": [r"DOOR_OPEN_RL", r"DOOR_AJAR_RL", r"DoorOpen_?RL",
                r"DOOR.*_RL\b", r"RL_DOOR"],
    "door_rr": [r"DOOR_OPEN_RR", r"DOOR_AJAR_RR", r"DoorOpen_?RR",
                r"DOOR.*_RR\b", r"RR_DOOR"],
    "turn_left": [
        r"TURN_SIGNAL_LEFT", r"LEFT_BLINKER", r"BLINKER_LEFT",
        r"TurnSignalLeft", r"LEFT_TURN", r"LAMP_LEFT",
    ],
    "turn_right": [
        r"TURN_SIGNAL_RIGHT", r"RIGHT_BLINKER", r"BLINKER_RIGHT",
        r"TurnSignalRight", r"RIGHT_TURN", r"LAMP_RIGHT",
    ],
    "brake": [
        r"^BRAKE_PRESSED$", r"BRAKE_PRESSED", r"BrakePressed",
        r"^BRAKE$", r"BRAKE_LIGHT", r"BRAKE_PEDAL",
    ],
    "seatbelt": [
        r"SEATBELT", r"SEAT_BELT", r"SeatBelt", r"BELT",
    ],
}

# Signals whose name matches these are never good dashboard sources
BLACKLIST = re.compile(
    r"CHECKSUM|COUNTER|CRC|_REQ$|REQUEST|SET_ME|UNKNOWN|NEW_SIGNAL|"
    r"ZORRO|RESERVED|SPARE",
    re.I,
)


# Warning-lamp / tell-tale signals. Mined separately from the 1:1 dashboard
# channels because a car may expose many of them and they are all booleans.
LAMP_PATTERNS = [
    ("ABS",       [r"ABS.*(LAMP|WARN|FAULT)", r"(LAMP|WARN).*ABS", r"ABS_?EVENT"]),
    ("AIRBAG",    [r"(AIRBAG|SRS).*(LAMP|WARN|FAULT)", r"AB_Lampe"]),
    ("ESP/TCS",   [r"(ESP|TCS|TRACTION|VSC|STABILITY).*(LAMP|OFF|FAULT|FLASH)"]),
    ("CHECK ENG", [r"(CHECK_?ENG|MIL|ENGINE).*(LAMP|WARN|FAULT)", r"DPF_LAMP"]),
    ("BATT",      [r"(BATT|CHARG|ALTERNATOR).*(LAMP|WARN|FAULT)"]),
    ("OIL",       [r"OIL.*(LAMP|WARN|PRESS)"]),
    ("COOLANT",   [r"(COOLANT|ENG_?TEMP).*(LAMP|WARN)"]),
    ("TPMS",      [r"TPMS.*(LAMP|WARN)", r"TIRE.*(LAMP|WARN)"]),
    ("BRAKE!",    [r"(BRAKE|EPB|PARK_?BRAKE|HANDBRAKE).*(LAMP|WARN|FAULT)"]),
    ("FUEL LOW",  [r"LOW_?FUEL", r"FUEL.*(LAMP|WARN)"]),
]


def mine_lamps(db, used_ids):
    """Find boolean warning-lamp signals. Returns {label: meta}."""
    out = {}
    for label, pats in LAMP_PATTERNS:
        for pat in pats:
            rx = re.compile(pat, re.I)
            hit = None
            for msg in db.messages:
                if msg.is_multiplexed() or not (0 < msg.length <= 8):
                    continue
                for sig in msg.signals:
                    if BLACKLIST.search(sig.name) or sig.length > 3:
                        continue
                    if rx.search(sig.name):
                        hit = (msg, sig)
                        break
                if hit:
                    break
            if hit:
                msg, sig = hit
                out[label] = sig_meta(msg, sig)
                break
        if len(out) >= 8:
            break
    return out


# channel -> (min_required_span, allow_unit_scaling)
# a signal whose full physical range can't even reach this is mislabeled
PLAUSIBLE = {
    "speed": 50.0,     # must reach at least 50 (mph or km/h)
    "rpm": 3000.0,     # a 5-bit field maxing at 31 is not an RPM signal
    "fuel": 10.0,
    "gear": 3.0,
}

# unit -> factor to convert into km/h
SPEED_UNITS = {
    "mph": 1.609344, "mi/h": 1.609344,
    "m/s": 3.6, "mps": 3.6,
    "kph": 1.0, "km/h": 1.0, "kmh": 1.0, "": 1.0,
}


def _plausible(ch, sig):
    need = PLAUSIBLE.get(ch)
    if need is None:
        return True
    if sig.is_signed:
        raw_hi = (1 << (sig.length - 1)) - 1
    else:
        raw_hi = (1 << sig.length) - 1
    span = abs(raw_hi * sig.scale)
    if ch == "speed":
        # allow for unit scaling: m/s signals legitimately max out lower
        span *= SPEED_UNITS.get((sig.unit or "").strip().lower(), 1.0)
    return span >= need


def pick(db, patterns, chan=None):
    """Return best (msg, sig, score) matching any pattern, or None."""
    best = None
    for prio, pat in enumerate(patterns):
        rx = re.compile(pat, re.I)
        for msg in db.messages:
            # multiplexed messages are painful to encode reliably - skip
            if msg.is_multiplexed():
                continue
            if msg.length == 0 or msg.length > 8:
                continue
            for sig in msg.signals:
                if BLACKLIST.search(sig.name):
                    continue
                if not rx.search(sig.name):
                    continue
                if chan and not _plausible(chan, sig):
                    continue
                score = prio
                cand = (msg, sig, score)
                if best is None or score < best[2]:
                    best = cand
        if best is not None:
            # found at this priority tier, don't look at weaker tiers
            break
    return best


def sig_meta(msg, sig):
    # physically representable range for this bit field
    if sig.is_signed:
        raw_lo, raw_hi = -(1 << (sig.length - 1)), (1 << (sig.length - 1)) - 1
    else:
        raw_lo, raw_hi = 0, (1 << sig.length) - 1
    phys_a = raw_lo * sig.scale + sig.offset
    phys_b = raw_hi * sig.scale + sig.offset
    phys_lo, phys_hi = min(phys_a, phys_b), max(phys_a, phys_b)

    lo, hi = sig.minimum, sig.maximum
    # some opendbc files declare ranges wider than the field can hold -> clamp
    lo = phys_lo if lo is None else max(float(lo), phys_lo)
    hi = phys_hi if hi is None else min(float(hi), phys_hi)
    if hi <= lo:
        lo, hi = phys_lo, phys_hi
    return {
        "message": msg.name,
        "frame_id": msg.frame_id,
        "is_extended": bool(msg.is_extended_frame),
        "dlc": msg.length,
        "signal": sig.name,
        "start_bit": sig.start,
        "length": sig.length,
        "byte_order": sig.byte_order,
        "is_signed": bool(sig.is_signed),
        "scale": float(sig.scale),
        "offset": float(sig.offset),
        "unit": sig.unit or "",
        "to_kmh": SPEED_UNITS.get((sig.unit or "").strip().lower(), 1.0),
        "min": float(lo),
        "max": float(hi),
    }


BO_RE = re.compile(r"^(BO_\s+)(\d+)(\s+)", re.M)


def _sanitize(text):
    """Several opendbc files declare >11-bit frame ids without setting the
    extended flag (bit 31), which cantools rejects. Set it for them."""
    def fix(m):
        fid = int(m.group(2))
        if 0x7FF < fid < 0x80000000:
            fid |= 0x80000000
        return f"{m.group(1)}{fid}{m.group(3)}"
    return BO_RE.sub(fix, text)


def _load(path):
    try:
        return cantools.database.load_file(path, strict=False), False
    except Exception:
        with open(path, "r", errors="replace") as fh:
            raw = fh.read()
        fixed = _sanitize(raw)
        if fixed == raw:
            raise
        return cantools.database.load_string(
            fixed, database_format="dbc", strict=False), True


def mine(path):
    name = os.path.splitext(os.path.basename(path))[0]
    try:
        db, patched = _load(path)
    except Exception as e:
        return None, f"parse-fail: {type(e).__name__}"
    if not getattr(db, "messages", None):
        return None, "no messages"

    chans, found = {}, []
    for ch, pats in CHANNELS.items():
        hit = pick(db, pats, ch)
        if hit:
            msg, sig, _ = hit
            chans[ch] = sig_meta(msg, sig)
            found.append(ch)

    used0 = {c["frame_id"] for c in chans.values()}
    lamps = mine_lamps(db, used0)

    # Many DBCs (Prius, Mercedes...) expose no warning-lamp signals at all.
    # Give those cars synthetic tell-tales on REAL-but-unused message IDs from
    # the same database, so every profile has lamps to discover and fuzz.
    if len(lamps) < 4:
        spare = [m for m in db.messages
                 if m.frame_id not in used0 and not m.is_extended_frame
                 and 0 < m.length <= 8 and m.frame_id <= 0x7FF]
        spare.sort(key=lambda m: m.frame_id)
        want = ["ABS", "AIRBAG", "ESP/TCS", "CHECK ENG",
                "BATT", "OIL", "COOLANT", "TPMS"]
        bit = 0
        for label in want:
            if label in lamps or not spare:
                continue
            msg = spare[0]
            lamps[label] = {
                "message": msg.name, "frame_id": msg.frame_id,
                "is_extended": bool(msg.is_extended_frame),
                "dlc": msg.length, "signal": f"SYN_{label.replace(' ', '_')}",
                "start_bit": bit, "length": 1, "byte_order": "little_endian",
                "is_signed": False, "scale": 1.0, "offset": 0.0,
                "unit": "", "min": 0.0, "max": 1.0, "to_kmh": 1.0,
                "synthetic": True,
            }
            bit += 1
            if bit >= msg.length * 8 or bit >= 8:
                spare.pop(0)
                bit = 0

    used = {c["frame_id"] for c in chans.values()}
    used |= {m["frame_id"] for m in lamps.values()}
    noise_ids = [m.frame_id for m in db.messages
                 if m.frame_id not in used and not m.is_extended_frame
                 and m.frame_id <= 0x7FF][:60]

    prof = {
        "name": name,
        "dbc": os.path.basename(path),
        "messages": len(db.messages),
        "channels": chans,
        "lamps": lamps,
        "coverage": sorted(found),
        "score": len(found),
        "patched_ext_ids": patched,
        "noise_ids": noise_ids,
    }
    return prof, None


def main():
    summary_only = "--summary" in sys.argv
    os.makedirs(PROF_DIR, exist_ok=True)
    files = sorted(glob.glob(os.path.join(DBC_DIR, "*.dbc")))
    rows, errs = [], []
    for f in files:
        prof, err = mine(f)
        if err:
            errs.append((os.path.basename(f), err))
            continue
        with open(os.path.join(PROF_DIR, prof["name"] + ".json"), "w") as fh:
            json.dump(prof, fh, indent=2)
        rows.append(prof)

    rows.sort(key=lambda r: (-r["score"], r["name"]))
    index = [
        {"name": r["name"], "dbc": r["dbc"], "score": r["score"],
         "messages": r["messages"], "coverage": r["coverage"]}
        for r in rows
    ]
    with open(os.path.join(PROF_DIR, "_index.json"), "w") as fh:
        json.dump(index, fh, indent=2)

    print(f"scanned {len(files)} dbc | profiles {len(rows)} | errors {len(errs)}")
    if summary_only:
        best = ", ".join(r["name"] for r in rows[:3])
        print(f"best coverage: {best}")
        return
    print(f"{'profile':44} {'msgs':>5} {'score':>5}  channels")
    print("-" * 110)
    for r in rows[:25]:
        print(f"{r['name']:44} {r['messages']:5} {r['score']:5}  "
              f"{','.join(r['coverage'])}")
    if errs:
        print("\nerrors:")
        for n, e in errs[:10]:
            print(f"  {n}: {e}")


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        # stdout was closed early (e.g. piped into `head`) - not an error
        try:
            sys.stdout.close()
        except Exception:
            pass
        os._exit(0)
