#!/usr/bin/env python3
"""Retain completed live solver-call costs by actual factor decision."""
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from compile_local_C_operators_v2 import digest, save
from record_qualification_progress_045 import process

root = Path(__file__).resolve().parents[2]; base = root/'build/timing400/release_001'
point = base/'DCO_domain_nom_tt27_c0_f247_80ns_bounded_reuse_gear_001'
launch_path = point/'launch.json'; launch = json.loads(launch_path.read_text())
identity = process(launch['pid']); assert identity['live'] and identity['argv'] == launch['command']
out = base/'live_DCO_factor_reuse_cost_review_001'; out.mkdir(exist_ok=False)
raw = (point/'native.log').read_bytes(); raw = raw[:raw.rfind(b'\n')+1]
snapshot = out/'native_log_prefix.log'; snapshot.write_bytes(raw)
decisions = {}; fallbacks = set(); calls = []
for line in raw.decode().splitlines():
    if not line.startswith('OpenPLL_wire_'): continue
    fields = dict(token.split('=',1) for token in line.split()[1:])
    call = int(fields['call'])
    if line.startswith('OpenPLL_wire_factor call='):
        assert call not in decisions
        decisions[call] = bool(int(fields['reused']))
    elif line.startswith('OpenPLL_wire_factor_refresh_after_nonpass call='):
        assert call not in fallbacks; fallbacks.add(call)
    elif line.startswith('OpenPLL_wire_PC call='):
        assert call == len(calls)+1 and int(fields['status']) == 0
        residual = float(fields['scaled_true_relative_residual'])
        assert math.isfinite(residual) and residual <= 1e-12
        seconds = float(fields['seconds']); assert math.isfinite(seconds) and seconds >= 0
        assert call in decisions
        if call in fallbacks: assert decisions[call]
        calls.append(dict(call=call, reused=decisions[call], fallback=call in fallbacks,
                          iterations=int(fields['iterations']), solve_wall_s=seconds))
assert calls and process(launch['pid'])['argv'] == identity['argv']
total = sum(c['solve_wall_s'] for c in calls)
groups = {}
for label in ('fresh_factor', 'reused_successfully', 'reused_then_fallback'):
    chosen = [c for c in calls if ('fresh_factor' if not c['reused'] else
              'reused_then_fallback' if c['fallback'] else 'reused_successfully') == label]
    wall = sum(c['solve_wall_s'] for c in chosen)
    groups[label] = dict(completed_calls=len(chosen), reported_solve_wall_s=wall,
         fraction_of_completed_solver_time=wall/total,
         mean_iterations=sum(c['iterations'] for c in chosen)/len(chosen) if chosen else None,
         mean_solve_wall_s=wall/len(chosen) if chosen else None)
save(out/'assessment.json', dict(input_sha256={str(p):digest(p) for p in (Path(__file__).resolve(),launch_path,snapshot)},
     observed_utc=datetime.now(timezone.utc).isoformat(), native_identity=identity,
     completed_solver_calls=len(calls), completed_solver_wall_s=total, groups=groups,
     pending_solver_calls_excluded=True, group_times_not_attributed_to_individual_internal_phases=True,
     physical_model_or_process_modified=False, proactive_refresh_speedup_demonstrated=False,
     full_DCO_qualified=False, release_qualified=False))
print(json.dumps(dict(completed_calls=len(calls), groups=groups)))
