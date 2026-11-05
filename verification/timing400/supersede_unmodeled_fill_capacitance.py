#!/usr/bin/env python3
"""Stop only the cap diagnostic whose overlaid fill purpose hides coupling."""
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import signal
import time
from run_dco_qualification import ROOT,sha,save
base=ROOT/'build/timing400/release_001';out=base/'parent_filled_metal_capacitance_extract_001'
control=base/'fill_capacitance_mapped_control_001/assessment.json';observations=json.loads(control.read_text())
assert observations['controls']['dual_purpose']['capacitor_records']==['C0 SIG VSUBS 6.09289f **FLOATING']
status=json.loads((out/'status.json').read_text());pid=status['native_pid'];owner=json.loads((out/'owner.json').read_text())
assert Path(f'/proc/{pid}/cwd').resolve()==out
assert int(Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()[1])==owner['runner_pid']
assert os.getpgid(pid)==pid
receipt=dict(observed_utc=datetime.now(timezone.utc).isoformat(),state='superseded_partial_not_device_failure',native_pid=pid,
    reason='Dual-purpose control proves retained FILL masks drawing-purpose conversion; use replacement of fill purpose instead of overlay.',
    control=str(control),control_sha256=sha(control),original_deadline_uptime=owner['deadline_uptime'],
    replacement_view_changes_purpose_representation=True,total_budget_restarted=False,automatic_identical_retry=False,release_qualified=False)
save(out/'superseded.json',receipt);os.killpg(pid,signal.SIGTERM)
for _ in range(100):
    p=Path(f'/proc/{pid}')
    if not p.exists() or (p/'stat').read_text().rsplit(')',1)[1].split()[0]=='Z':break
    time.sleep(.1)
else:raise AssertionError('native diagnostic did not stop')
print('Stopped only superseded CAD cap extraction; no analog jobs or manufacturing GDS changed.')
