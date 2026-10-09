# Third-party DBC files

Every `.dbc` file in this directory is redistributed unmodified from
[commaai/opendbc](https://github.com/commaai/opendbc).

**Copyright (c) 2020, Comma.ai, Inc. — MIT License.**

Full license text: https://github.com/commaai/opendbc/blob/master/LICENSE

These files are what make this simulator's CAN IDs and bit layouts real rather
than invented. When the lab says a 2010 Prius reports speed on `0x0B4`, that
fact comes from `toyota_prius_2010_pt.dbc` as published by comma.ai.

No DBC content has been altered. `scripts/mine_dbc.py` reads them and emits the
derived JSON profiles in `profiles/`; the DBCs themselves are untouched.
