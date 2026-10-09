#!/usr/bin/env bash
# Check that everything this lab needs is present, and say exactly how to get
# anything that is missing. Safe to run any time; changes nothing.
cd "$(dirname "$0")"

PASS=0
WARN=0
FAIL=0

ok()   { echo "  [ OK ] $1"; PASS=$((PASS+1)); }
warn() { echo "  [WARN] $1"; WARN=$((WARN+1)); }
bad()  { echo "  [FAIL] $1"; FAIL=$((FAIL+1)); }

echo "== 1. Python =="
if command -v python3 >/dev/null 2>&1; then
    PYV=$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')
    PYOK=$(python3 -c 'import sys; print(1 if sys.version_info >= (3,9) else 0)')
    if [ "$PYOK" = "1" ]; then ok "python3 $PYV"; else
        bad "python3 $PYV is too old - need 3.9+"
    fi
else
    bad "python3 not found     ->  sudo apt install python3 python3-venv"
fi

python3 -c 'import venv' 2>/dev/null \
    && ok "python3-venv module" \
    || bad "python3-venv missing ->  sudo apt install python3-venv"

echo
echo "== 2. Python packages (from requirements.txt) =="
if [ -x ./.venv/bin/python ]; then
    PY=./.venv/bin/python
    ok "venv exists at ./.venv"
else
    PY=python3
    warn "no ./.venv yet       ->  run ./setup.sh"
fi
for mod in can cantools pygame msgpack; do
    if $PY -c "import $mod" 2>/dev/null; then
        ok "import $mod"
    else
        bad "import $mod failed  ->  ./setup.sh   (installs requirements.txt)"
    fi
done

echo
echo "== 3. can-utils (needed for candump / cansend exercises) =="
for t in candump cansend cangen; do
    command -v $t >/dev/null 2>&1 \
        && ok "$t" \
        || bad "$t missing        ->  sudo apt install can-utils"
done

echo
echo "== 4. CaringCaribou (the attack tool the lab is built around) =="
if command -v caringcaribou >/dev/null 2>&1; then
    ok "caringcaribou $(caringcaribou --help 2>&1 | grep -oE 'v[0-9]+\.[0-9]+' | head -1)"
elif command -v cc.py >/dev/null 2>&1; then
    ok "cc.py (older CaringCaribou entry point)"
else
    bad "caringcaribou missing ->  pipx install caringcaribou"
    echo "         or:  pip install --user caringcaribou"
    echo "         or:  git clone https://github.com/CaringCaribou/caringcaribou"
fi

echo
echo "== 5. vcan kernel module (needed for socketcan mode) =="
if modinfo vcan >/dev/null 2>&1; then
    ok "vcan module available"
else
    warn "vcan module not found - your kernel may lack SocketCAN"
    echo "         Debian/Ubuntu:  sudo apt install linux-modules-extra-\$(uname -r)"
    echo "         WSL2 / some VPS kernels do not ship vcan at all."
    echo "         Fallback with no root and no vcan:  ./run.sh -i udp"
fi

if ip link show vcan0 >/dev/null 2>&1; then
    ok "vcan0 interface is up"
else
    warn "vcan0 not up         ->  sudo ./setup_vcan.sh   (once per boot)"
    echo "         Without vcan0, CaringCaribou and candump cannot be used."
    echo "         ./run.sh -i udp still works with no root at all."
fi

echo
echo "== 6. Lab data =="
NPROF=$(ls profiles/*.json 2>/dev/null | grep -vc '_index' || echo 0)
NDBC=$(ls dbc/*.dbc 2>/dev/null | wc -l)
[ "$NDBC" -ge 50 ] && ok "$NDBC DBC files" || bad "only $NDBC DBC files - incomplete clone?"
if [ "$NPROF" -ge 50 ]; then
    ok "$NPROF car profiles"
else
    warn "only $NPROF profiles   ->  ./setup.sh   (mines them from dbc/)"
fi

echo
echo "-----------------------------------------------"
echo "  $PASS ok, $WARN warnings, $FAIL failures"
if [ "$FAIL" -gt 0 ]; then
    echo "  Fix the [FAIL] lines above before the lab."
    exit 1
elif [ "$WARN" -gt 0 ]; then
    echo "  Usable, but read the [WARN] lines - some exercises may be blocked."
    exit 0
else
    echo "  Ready. Next:  ./run.sh     then see the README"
    exit 0
fi
