#!/usr/bin/env bash
# Signal-handling regression: every script must clean up on INT and TERM.
# NOTE: bash sets non-interactive background jobs' SIGINT to SIG_IGN, so we
# run each child under setsid in its own session to get realistic delivery.
cd "$(dirname "$0")/.."
PY=./.venv/bin/python
FAIL=0

run_case() {
    local name="$1" sig="$2" logf="$3"; shift 3
    setsid "$@" >"$logf" 2>&1 &
    local pid=$!
    sleep 2
    kill -"$sig" "$pid" 2>/dev/null
    sleep 2

    local leak tb clean
    leak=$(grep -c "not properly shut down" "$logf" 2>/dev/null)
    tb=$(grep -c "Traceback" "$logf" 2>/dev/null)
    # a clean exit prints either "[+] stopped" or a final summary line
    clean=$(grep -cE "\[\+\] stopped|\[\+\] sent|\[\+\] frames" "$logf" 2>/dev/null)

    if [ "$leak" = "0" ] && [ "$tb" = "0" ] && [ "$clean" != "0" ]; then
        echo "  [PASS] $name on SIG$sig"
    else
        echo "  [FAIL] $name on SIG$sig - leak=$leak traceback=$tb clean=$clean"
        tail -3 "$logf" | sed 's/^/         /'
        FAIL=1
    fi
    kill -9 "$pid" 2>/dev/null
    wait "$pid" 2>/dev/null
}

echo "== signal handling =="
for sig in INT TERM; do
    run_case "dash.py  headless" "$sig" /tmp/sig_dash.log \
        $PY scripts/dash.py -i udp -c prius --headless 30
    run_case "sim.py   headless" "$sig" /tmp/sig_sim.log \
        $PY scripts/sim.py -i udp -c prius --headless 30
    run_case "attack.py spoof  " "$sig" /tmp/sig_atk.log \
        $PY scripts/attack.py -i udp spoof -c prius --channel speed --value 100 --rate 20
done

echo "== run.sh child reaping =="
pgrep -f "scripts/(dash|sim)\.py" >/dev/null 2>&1 && \
    pkill -f "scripts/(dash|sim)\.py" 2>/dev/null; sleep 1

./run.sh -i udp -c prius >/tmp/sig_run.log 2>&1 &
RUNPID=$!
sleep 4
BEFORE=$(pgrep -f "scripts/(dash|sim)\.py" 2>/dev/null | wc -l)
kill -TERM $RUNPID 2>/dev/null
sleep 4
AFTER=$(pgrep -f "scripts/(dash|sim)\.py" 2>/dev/null | wc -l)
if [ "$BEFORE" -ge 2 ] && [ "$AFTER" = "0" ]; then
    echo "  [PASS] run.sh reaps children on SIGTERM ($BEFORE -> $AFTER)"
else
    echo "  [FAIL] run.sh orphaned children ($BEFORE -> $AFTER)"
    FAIL=1
fi
pkill -f "scripts/(dash|sim)\.py" 2>/dev/null
wait 2>/dev/null

echo
[ $FAIL -eq 0 ] && echo "SIGNAL HANDLING OK" || echo "SIGNAL HANDLING FAILED"
exit $FAIL
