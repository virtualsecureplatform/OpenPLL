#!/usr/bin/env python3
"""Retire a changed-scope route attempt with a fixed-wire/keepout conflict."""
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import signal
import time
from run_dco_qualification import ROOT,sha,save

base=ROOT/'build/timing400/release_001';old=base/'parent_dco_antenna_targeted_007'
status=json.loads((old/'status.json').read_text());pid=status['native_pid']
argv=Path(f'/proc/{pid}/cmdline').read_bytes().split(b'\0');assert str(old/'route.tcl').encode() in argv
assert os.getpgid(pid)==pid
receipt=dict(observed_utc=datetime.now(timezone.utc).isoformat(),classification='superseded_partial_not_device_failure',native_pid=pid,
    reason='Temporary M1 keepout intersects immutable COARSETHERMAL_CODE[22] via landing; reroute that additional net instead of spending remaining routing iterations on a fixed conflict.',
    original_deadline_uptime=json.loads((old/'owner.json').read_text())['deadline_uptime'],
    replacement_targets_add=['COARSETHERMAL_CODE[22]'],native_analog_jobs_untouched=True,total_budget_restarted=False,
    automatic_identical_retry=False,release_qualified=False)
save(old/'supersession_requested.json',receipt)
os.killpg(pid,signal.SIGTERM)
for _ in range(100):
    process=Path(f'/proc/{pid}')
    if not process.exists() or (process/'stat').read_text().rsplit(')',1)[1].split()[0]=='Z':break
    time.sleep(.1)
else:raise AssertionError('native route failed to terminate')
receipt['evidence_sha256']={str(p):sha(p) for p in [Path(__file__).resolve(),old/'route.tcl',old/'route.log',old/'input_manifest.json',base/'parent_dco_antenna_port_topology_004/assessment.json']}
save(old/'superseded.json',receipt)
save(old/'status.json',dict(state='superseded_partial',native_pid=pid,release_qualified=False))
print('Stopped only superseded route007; original deadline and all four analog jobs preserved.')
