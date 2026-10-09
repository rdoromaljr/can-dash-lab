#!/usr/bin/env bash
# Build the venv and mine the car profiles. Safe to re-run.
set -e
cd "$(dirname "$0")"
[ -d .venv ] || python3 -m venv .venv
./.venv/bin/pip -q install --upgrade pip
./.venv/bin/pip -q install -r requirements.txt
echo "[+] deps installed"
./.venv/bin/python scripts/mine_dbc.py --summary
echo
echo "[+] done. next:"
echo "      sudo ./setup_vcan.sh && ./run.sh     # realistic (socketcan)"
echo "      ./run.sh -i udp                      # no root needed"
echo "      ./verify.sh                          # self test"
