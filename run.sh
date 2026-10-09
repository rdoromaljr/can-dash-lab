#!/usr/bin/env bash
# Launch the cluster + controls together.
#   ./run.sh                    prius on vcan0
#   ./run.sh -c mercedes        pick a car
#   ./run.sh -i udp             no-root bus (no sudo needed)
#   ./run.sh --list             show all cars
cd "$(dirname "$0")"
PY=./.venv/bin/python
CAR=toyota_prius_2010_pt
IFACE=vcan0
EXTRA=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    -c|--car) CAR="$2"; shift 2;;
    -i|--interface) IFACE="$2"; shift 2;;
    --list) $PY scripts/sim.py --list; exit 0;;
    *) EXTRA+=("$1"); shift;;
  esac
done

if [[ "$IFACE" != "udp" && "$IFACE" != "virtual" ]]; then
  if ! ip link show "$IFACE" >/dev/null 2>&1; then
    echo "[!] $IFACE does not exist."
    echo "    run:  sudo ./setup_vcan.sh $IFACE"
    echo "    or:   ./run.sh -i udp      (no root required)"
    exit 1
  fi
fi

DASH=""
SIM=""

# Make sure neither child outlives this script, however we exit:
# normal end, Ctrl-C, or SIGTERM from `timeout`/`kill`.
cleanup() {
  trap - EXIT INT TERM HUP
  for p in "$SIM" "$DASH"; do
    [ -n "$p" ] && kill -TERM "$p" 2>/dev/null
  done
  # give them a moment to close their CAN sockets cleanly
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    kill -0 "$DASH" 2>/dev/null || kill -0 "$SIM" 2>/dev/null || break
    sleep 0.2
  done
  for p in "$SIM" "$DASH"; do
    [ -n "$p" ] && kill -9 "$p" 2>/dev/null
  done
  wait 2>/dev/null
}
trap cleanup EXIT INT TERM HUP

echo "[+] car=$CAR iface=$IFACE"
$PY scripts/dash.py -i "$IFACE" -c "$CAR" "${EXTRA[@]}" &
DASH=$!
sleep 1

# Bail out early if the cluster died (bad iface, missing dep, ...)
if ! kill -0 "$DASH" 2>/dev/null; then
  echo "[!] the cluster failed to start - see the error above."
  exit 1
fi

$PY scripts/sim.py -i "$IFACE" -c "$CAR" "${EXTRA[@]}" &
SIM=$!
wait "$SIM"
