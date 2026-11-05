#!/usr/bin/env python3
"""Stop recent numerical probes so the failed TT100 range gate is resolved first."""
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import signal
import time
from run_dco_qualification import ROOT,sha,save
base=ROOT/'build/timing400/release_001';range_path=base/'tt100_endpoint_collection_001/assessment.json'
r=json.loads(range_path.read_text());assert r['both_native_endpoints_collected'] and not r['intrinsic_tt100_ordered_range_brackets_target']
assert r['cases']['8']['metric']['mhz']>100
records=[]
for code in [128,247]:
    folder=base/f'dco_duration_c1_f{code}_160ns_step5_001';state=json.loads((folder/'status.json').read_text());owner=json.loads((folder/'owner.json').read_text())
    assert state['state']=='native_running';pid=state['native_pid'];p=Path('/proc')/str(pid)
    argv=[x.decode() for x in (p/'cmdline').read_bytes().split(b'\0') if x]
    assert str(folder/'duration.spice') in argv and os.getpgid(pid)==pid
    assert int((p/'stat').read_text().rsplit(')',1)[1].split()[1])==owner['runner_pid']
    record=dict(observed_utc=datetime.now(timezone.utc).isoformat(),classification='superseded_partial_for_range_gate',native_pid=pid,
        reason='TT100 coarse13 does not bracket100MHz; neighboring coarse14 range observations precede further calibration.',
        prior_deadline_uptime=owner['absolute_deadline_uptime'],budget_not_restarted=True,identical_native_retry_not_authorized=True,
        range_evidence=str(range_path),range_evidence_sha256=sha(range_path),release_qualified=False)
    save(folder/'range_gate_superseded.json',record);os.killpg(pid,signal.SIGTERM)
    for _ in range(100):
        if not p.exists() or (p/'stat').read_text().rsplit(')',1)[1].split()[0]=='Z':break
        time.sleep(.1)
    else:raise AssertionError('native probe did not terminate')
    records.append(record)
out=base/'tt100_range_priority_handoff_001';out.mkdir(exist_ok=False)
save(out/'assessment.json',dict(input_sha256={str(Path(__file__).resolve()):sha(Path(__file__).resolve()),str(range_path):sha(range_path)},
    artifacts={},stopped_step_probes=records,preserved_duration_baselines=[3883557,3883676],
    next_native_cases=dict(coarse=14,fine=[8,247],stop_ns=80,pvt=dict(corner='tt',temperature_c=27,supply_v=1.8)),
    release_qualified=False,scope=__doc__))
print('Retained both partial numerical probes; two analog slots available for the adjacent TT100 band.')
