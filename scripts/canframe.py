#!/usr/bin/env python3
"""
canframe.py - DBC-accurate signal packing/unpacking.

Implements both bit orderings used in DBC files:
  little_endian ("Intel", @1)   - start bit is the LSB, bits ascend
  big_endian    ("Motorola", @0) - start bit is the MSB, sawtooth layout

Keeping this standalone (no cantools at runtime) means the simulator and the
dashboard stay light and you can read exactly how a CAN signal is
laid out inside 8 bytes.
"""

__all__ = ["encode_signal", "decode_signal", "raw_to_phys", "phys_to_raw"]


def _bit_positions(start, length, byte_order):
    """Yield absolute bit indices (byte*8 + bit) from MSB..LSB of the signal."""
    if byte_order == "little_endian":
        # Intel: start = LSB, walk upward; emit MSB first
        return [start + i for i in range(length)][::-1]
    # Motorola / big_endian: start = MSB. Within a byte bits go 7..0,
    # and when we run off the bottom of a byte we continue at bit 7
    # of the *next* byte.
    pos, out = start, []
    for _ in range(length):
        out.append(pos)
        if pos % 8 == 0:
            pos += 15      # drop to next byte, back up to bit 7
        else:
            pos -= 1
    return out


def _get_bit(data, idx):
    return (data[idx // 8] >> (idx % 8)) & 1


def _set_bit(data, idx, val):
    byte, bit = idx // 8, idx % 8
    if val:
        data[byte] |= (1 << bit)
    else:
        data[byte] &= ~(1 << bit) & 0xFF


def decode_raw(data, meta):
    """Extract the raw integer of a signal from frame bytes."""
    bits = _bit_positions(meta["start_bit"], meta["length"], meta["byte_order"])
    raw = 0
    for idx in bits:                      # MSB -> LSB
        if idx // 8 >= len(data):
            return 0
        raw = (raw << 1) | _get_bit(data, idx)
    if meta.get("is_signed") and raw >= (1 << (meta["length"] - 1)):
        raw -= (1 << meta["length"])
    return raw


def encode_raw(data, meta, raw):
    """Write a raw integer into a mutable bytearray frame."""
    length = meta["length"]
    if meta.get("is_signed"):
        lo, hi = -(1 << (length - 1)), (1 << (length - 1)) - 1
    else:
        lo, hi = 0, (1 << length) - 1
    raw = max(lo, min(hi, int(raw)))
    if raw < 0:
        raw += (1 << length)
    bits = _bit_positions(meta["start_bit"], length, meta["byte_order"])
    for n, idx in enumerate(bits):        # MSB -> LSB
        if idx // 8 >= len(data):
            continue
        _set_bit(data, idx, (raw >> (length - 1 - n)) & 1)
    return data


def raw_to_phys(raw, meta):
    return raw * meta["scale"] + meta["offset"]


def phys_to_raw(value, meta):
    scale = meta["scale"] or 1.0
    return int(round((value - meta["offset"]) / scale))


def decode_signal(data, meta):
    return raw_to_phys(decode_raw(data, meta), meta)


def encode_signal(data, meta, value):
    lo, hi = meta.get("min"), meta.get("max")
    if lo is not None and hi is not None and hi > lo:
        value = max(lo, min(hi, value))
    return encode_raw(data, meta, phys_to_raw(value, meta))
