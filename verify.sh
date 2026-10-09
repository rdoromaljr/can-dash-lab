#!/usr/bin/env bash
# End-to-end self test. Uses the no-root udp bus so it works anywhere.
cd "$(dirname "$0")"
PY=./.venv/bin/python
FAIL=0
ok(){ echo "  [PASS] $1"; }
no(){ echo "  [FAIL] $1"; FAIL=1; }

echo "== 1. deps =="
for m in can cantools pygame msgpack; do
  $PY -c "import $m" 2>/dev/null && ok "import $m" || no "import $m (pip install -r requirements.txt)"
done

echo "== 2. profiles =="
N=$($PY -c "import json;print(len(json.load(open('profiles/_index.json'))))" 2>/dev/null)
[ "${N:-0}" -ge 50 ] && ok "$N car profiles" || no "only ${N:-0} profiles"

echo "== 3. bit packing round-trip =="
$PY scripts/verify_profiles.py >/tmp/icsim_rt.log 2>&1 && ok "$(tail -1 /tmp/icsim_rt.log)" || no "$(tail -1 /tmp/icsim_rt.log)"

echo "== 4. packing matches cantools =="
$PY - <<'EOF' >/tmp/icsim_ct.log 2>&1
import sys,random,cantools,glob; sys.path.insert(0,'scripts')
from canframe import decode_signal
random.seed(1); bad=tot=0
for f in sorted(glob.glob('dbc/*.dbc'))[:12]:
    try: db=cantools.database.load_file(f,strict=False)
    except Exception: continue
    for msg in list(db.messages)[:25]:
        if msg.is_multiplexed() or msg.length>8 or msg.length==0: continue
        for sig in msg.signals:
            meta=dict(start_bit=sig.start,length=sig.length,byte_order=sig.byte_order,
                      is_signed=bool(sig.is_signed),scale=float(sig.scale),
                      offset=float(sig.offset),dlc=msg.length)
            for _ in range(3):
                data=bytes(random.getrandbits(8) for _ in range(msg.length))
                try: ref=msg.decode(data,decode_choices=False,allow_truncated=True).get(sig.name)
                except Exception: continue
                if ref is None: continue
                tot+=1
                if abs(float(ref)-decode_signal(data,meta))>abs(sig.scale)*1e-6+1e-9: bad+=1
print(f"{tot-bad}/{tot} signals match cantools")
sys.exit(1 if bad else 0)
EOF
[ $? -eq 0 ] && ok "$(cat /tmp/icsim_ct.log)" || no "$(cat /tmp/icsim_ct.log)"

echo "== 5. sim -> dash end to end =="
$PY scripts/dash.py -i udp -c prius --headless 9 >/tmp/icsim_dash.log 2>&1 &
DP=$!
sleep 2
$PY - <<'EOF' >/tmp/icsim_sim.log 2>&1
import sys,time; sys.path.insert(0,'scripts')
from bus import open_bus
from common import load_profile
from sim import Vehicle, Transmitter
p=load_profile("toyota_prius_2010_pt"); b=open_bus("udp")
tx=Transmitter(b,p,noise=False); v=Vehicle()
last=t0=time.time()
while time.time()-t0<3.0:
    now=time.time(); dt=now-last
    if dt<0.02: time.sleep(0.02-dt); continue
    last=now; v.throttle=1.0; v.doors[2]=True; v.step(dt); tx.send(v,now)
print(f"SENT={tx.tx} SPEED={v.speed:.1f} RPM={v.rpm:.0f}")
time.sleep(2); b.shutdown()
EOF
wait $DP
SENT=$(grep -o 'SENT=[0-9]*' /tmp/icsim_sim.log|cut -d= -f2)
GOT=$(grep -o 'frames=[0-9]*' /tmp/icsim_dash.log|cut -d= -f2)
SSP=$(grep -o 'SPEED=[0-9.]*' /tmp/icsim_sim.log|cut -d= -f2)
DSP=$(grep -o 'speed=[0-9.]*' /tmp/icsim_dash.log|cut -d= -f2)
[ -n "$SENT" ] && [ "$SENT" = "$GOT" ] && ok "frames $SENT sent = $GOT received (0 loss)" || no "frames sent=$SENT received=$GOT"
$PY -c "import sys;a=float('$SSP' or 0);b=float('$DSP' or -1);sys.exit(0 if abs(a-b)<1.5 else 1)" \
  && ok "speed sim=$SSP km/h = dash=$DSP km/h" || no "speed sim=$SSP dash=$DSP"
grep -q 'doors=\[False, False, True, False\]' /tmp/icsim_dash.log && ok "door RL decoded correctly" || no "door state wrong: $(grep -o 'doors=\[[^]]*\]' /tmp/icsim_dash.log)"

echo "== 6. spoof reaches the cluster =="
$PY scripts/dash.py -i udp -c prius --headless 7 >/tmp/icsim_spoof.log 2>&1 &
DP=$!
sleep 2
$PY scripts/attack.py -i udp spoof -c prius --channel doors --value 15 --rate 60 --seconds 2 >/dev/null 2>&1
sleep 3; wait $DP
grep -q 'doors=\[True, True, True, True\]' /tmp/icsim_spoof.log && ok "spoofed all 4 doors open while car is off" || no "spoof failed: $(grep -o 'doors=\[[^]]*\]' /tmp/icsim_spoof.log)"

echo "== 7. warning lamps react to injection =="
LAMPID=$($PY -c "
import json;d=json.load(open('profiles/toyota_prius_2010_pt.json'))
m=list(d['lamps'].values())[0];print('%03X'%m['frame_id'])" 2>/dev/null)
$PY scripts/dash.py -i udp -c prius --headless 9 >/tmp/icsim_lamp.log 2>&1 &
LD=$!
sleep 2
$PY - <<EOF >/dev/null 2>&1
import sys,time,json; sys.path.insert(0,'scripts')
from bus import open_bus
from canframe import encode_signal
import can
d=json.load(open('profiles/toyota_prius_2010_pt.json'))
lamps=d['lamps']; names=list(lamps)[:2]
b=open_bus('udp')
buf=bytearray(lamps[names[0]]['dlc'])
for n in names: encode_signal(buf, lamps[n], 1)
for _ in range(20):
    b.send(can.Message(arbitration_id=lamps[names[0]]['frame_id'],
                       is_extended_id=False, data=bytes(buf)))
    time.sleep(0.02)
b.send(can.Message(arbitration_id=0x666, is_extended_id=False, data=b'\xde'*8))
time.sleep(1); b.shutdown()
print(','.join(names))
EOF
sleep 4; wait $LD
LIT=$(grep -o "LAMPS_EVER_LIT=\[[^]]*\]" /tmp/icsim_lamp.log)
ROGUE=$(grep -o "ROGUE_IDS=[0-9]*" /tmp/icsim_lamp.log | cut -d= -f2)
if echo "$LIT" | grep -q "'" && [ "${ROGUE:-0}" -ge 1 ]; then
  ok "injected lamps lit: $LIT ; rogue IDs detected: $ROGUE"
else
  no "lamp injection failed: $LIT rogue=$ROGUE"
fi

echo "== 8. signal handling + child reaping =="
if ./scripts/verify_signals.sh >/tmp/icsim_sig.log 2>&1; then
  NP=$(grep -c '\[PASS\]' /tmp/icsim_sig.log)
  ok "$NP/$NP clean shutdowns (INT+TERM x3 scripts, + run.sh reaping)"
else
  no "signal handling: $(grep '\[FAIL\]' /tmp/icsim_sig.log | head -2 | tr '\n' ' ')"
fi

echo
[ $FAIL -eq 0 ] && echo "ALL CHECKS PASSED" || echo "SOME CHECKS FAILED"
exit $FAIL
