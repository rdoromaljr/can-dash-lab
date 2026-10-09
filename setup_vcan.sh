#!/usr/bin/env bash
# Create a virtual CAN interface for the simulator. Needs sudo once per boot.
set -e
IF="${1:-vcan0}"
sudo modprobe vcan
if ! ip link show "$IF" >/dev/null 2>&1; then
    sudo ip link add dev "$IF" type vcan
fi
sudo ip link set up "$IF"
echo "[+] $IF is up:"
ip -br link show "$IF"
echo
echo "Next:"
echo "  ./run.sh                 # simulator + dashboard"
echo "  candump $IF              # watch raw traffic"
