#!/usr/bin/env python3
"""Reassess retained native output without rerunning or rewriting its receipt."""
import json
from pathlib import Path
import time
from compile_local_C_operators_v2 import digest, save
from assess_compact_numerical_holdout_v2 import assess

root=Path(__file__).resolve().parents[2]
base=root/'build/timing400/release_001'
source=base/'selected_compact_numerical_holdouts_sf_m40_001/relative_tolerance_only'
run=source/'run_001'
owner=json.loads((source.parent/'owner.json').read_text())
deadline=owner['deadline_uptime']
assert time.clock_gettime(time.CLOCK_BOOTTIME)<deadline
assert json.loads((run/'native_exit.json').read_text())['native_exit']==0
assert json.loads((run/'runner_failure.json').read_text())['error_type']=='AssertionError'
launch=json.loads((run/'launch.json').read_text())
pins=dict(launch['input_sha256'])
for path, sha in pins.items(): assert digest(Path(path))==sha,path
out=base/'relative_tolerance_printed_time_reassessment_001'
out.mkdir(exist_ok=False)
for p in (Path(__file__).resolve(),Path(__file__).with_name('assess_compact_numerical_holdout_v2.py'),
          run/'batch.prn',run/'native_exit.json',run/'runner_failure.json',run/'launch.json'):
    pins[str(p)]=digest(p)
(out/'batch.prn').symlink_to(run/'batch.prn')
save(out/'recovery_scope.json',dict(original_run=str(run),native_rerun=False,
    original_receipt_modified=False,deadline_uptime=deadline,
    equal_time_samples_retained=True,unresolved_threshold_crossings_rejected=True,
    printed_time_precision_is_not_transient_error_bound=True,release_qualified=False))
assess(json.loads((source/'plan.json').read_text()),pins,out,deadline)
