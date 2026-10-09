# Credits and Prior Art

This project stands on other people's work. This page says exactly whose, what
was taken, and what was not — both because they earned the credit and because
licenses demand precision.

---

## ICSim — Craig Smith (@zombieCraig)

**https://github.com/zombieCraig/ICSim** — GPL-3.0

**ICSim is the reason this project exists.** Craig Smith built the original
instrument cluster simulator and, with it, taught a generation of people that
you can learn CAN bus attacks on a laptop with no car, no CAN adapter, and no
budget. The pedagogy here is his: a fake dashboard, a virtual bus, and the
realisation that the cluster cannot tell your injected frame from the real
ECU's. Every exercise in this repository is a variation on that one insight.

Craig also wrote *The Car Hacker's Handbook* (No Starch Press), which remains
the standard text. If this simulator is useful to you, read it.

### What was taken, and what was not

**Taken:** the *concept*. A passive cluster, a vehicle simulator, a virtual bus,
and the "find which ID controls the thing" bisection exercise.

**Not taken: any code.** ICSim is C against SDL. This project is Python against
pygame and `python-can`, written from scratch. Specifically:

- No ICSim source file is present, vendored, ported, or translated here.
- ICSim's arbitration IDs — `0x244` (speed), `0x19B` (doors), `0x188` (turn
  signals) — appear nowhere in this repository. They are invented for teaching.
  The IDs used here are the real ones, from opendbc (see below).
- The signal packing in `scripts/canframe.py` is an independent implementation
  of the DBC layout rules (Intel and Motorola bit orderings), verified against
  `cantools` rather than against ICSim.

**On licensing:** ICSim is GPL-3.0 and this project is MIT. That is only
legitimate because no ICSim code was copied — copyright covers expression, not
ideas, so the concept is free to build on while the implementation is not. Had
any ICSim source been reused, this project would be obligated to be GPL-3.0 too.
It contains none.

---

## opendbc — comma.ai

**https://github.com/commaai/opendbc** — MIT, Copyright (c) 2020 Comma.ai, Inc.

**opendbc is what makes this simulator honest.** The 58 `.dbc` files in `dbc/`
are comma.ai's, redistributed unmodified. They are the result of an enormous
community reverse-engineering effort across dozens of manufacturers.

Without them, every CAN ID in this lab would be made up, and you would be
learning a fictional protocol. Because of them:

- `0x0B4` really is where a 2010 Prius reports speed
- `SPEED.SPEED` really is 16 bits, big-endian, start bit 47, scaled 0.0062 mph
- all **54 vehicle profiles** here describe real vehicles, and switching from
  the Prius to the Mercedes really does change every ID and bit offset

That last point is the single most valuable teaching property of this lab, and
it is entirely comma.ai's contribution.

**What was taken:** the `.dbc` files, unmodified, redistributed under MIT with
this notice. See [`dbc/NOTICE.md`](dbc/NOTICE.md).

**What was built here:** `scripts/mine_dbc.py` reads those DBCs and derives the
JSON profiles in `profiles/`, scoring each vehicle by how many dashboard
channels it can populate. The DBC files themselves are untouched.

---

## CaringCaribou — Kasper Karlsson, Tobias Lans et al. (CaringCaribou project)

**https://github.com/CaringCaribou/caringcaribou** — GPL-3.0

The attack toolchain this lab is designed around. `listener`, `dump`, `send`,
`fuzzer`, and `uds` are the tools this simulator is built to be attacked with.

CaringCaribou is **not** bundled, vendored, or modified here — you install it
separately and point it at this simulator's virtual bus. This repository is a
*target* for it, not a derivative of it, so its GPL-3.0 does not extend to this
project.

---

## can-utils — Linux kernel SocketCAN project

**https://github.com/linux-can/can-utils** — GPL-2.0 / BSD-3-Clause

`candump`, `cansend`, `cangen`, and the `vcan` kernel module. Same relationship
as CaringCaribou: used as external tools, not bundled.

---

## Python libraries

| Library | License | Role |
|---|---|---|
| [python-can](https://github.com/hardbyte/python-can) | LGPL-3.0 | Bus abstraction — socketcan, udp_multicast, virtual |
| [cantools](https://github.com/cantools/cantools) | MIT | DBC parsing in `mine_dbc.py`; independent oracle in `verify.sh` |
| [pygame](https://github.com/pygame/pygame) | LGPL-2.1 | Cluster and control panel rendering |
| [msgpack](https://github.com/msgpack/msgpack-python) | Apache-2.0 | Required by python-can's `udp_multicast` bus |

All used as unmodified dependencies via `pip`, not vendored.

---

## Summary

| Project | License | Relationship |
|---|---|---|
| ICSim | GPL-3.0 | **Conceptual inspiration. No code reused.** |
| opendbc | MIT | **58 DBC files redistributed unmodified.** |
| CaringCaribou | GPL-3.0 | External tool. Not bundled. |
| can-utils | GPL-2.0 / BSD-3 | External tools. Not bundled. |
| python-can, cantools, pygame, msgpack | various | pip dependencies. Not vendored. |

If you believe anything here is mis-credited or mis-licensed, please open an
issue. Getting this right matters more than the code does.
