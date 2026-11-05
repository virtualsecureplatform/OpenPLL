#!/usr/bin/env python3
"""Validate instrumentation-only source diff and retain offline phase timings."""
import json
from pathlib import Path
import re
from compile_local_C_operators_v2 import digest, save

root = Path(__file__).resolve().parents[2]
base = root/'build/timing400/release_001'
case = base/'native_bounded_reuse_stage_probe_checks_001'
assessment = case/'assessment.json'; proof = json.loads(assessment.read_text())
assert proof['all_original_equation_residual_checks_passed'] and len(proof['checks']) == 16
header = root/'verification/timing400/native_bounded_reuse_stage_probe/OpenPLL_WirePreconditioner_warm_reuse_bounded.h'
original = root/'verification/timing400/native_wire_preconditioner/OpenPLL_WirePreconditioner_warm_reuse_bounded.h'
changed = header.read_text()
block = '''
        auto phase_begin=begin;
        auto checkpoint=[&](const char* phase) {
            auto now=std::chrono::steady_clock::now();
            std::cout << "OpenPLL_wire_stage call=" << calls_+1 << " phase=" << phase
                << " seconds=" << std::setprecision(17)
                << std::chrono::duration<double>(now-phase_begin).count() << std::endl;
            phase_begin=std::chrono::steady_clock::now();
        };'''
assert changed.count(block) == 1
changed = changed.replace(block, '')
changed, removed = re.subn(r'        checkpoint\("\w+"\);\n', '', changed)
assert removed == 8 and changed == original.read_text(), 'instrumentation changes numerical source'
phases = {}; records = []
for line in (case/'probe.log').read_text().splitlines():
    if line.startswith('OpenPLL_wire_stage '):
        fields = dict(token.split('=', 1) for token in line.split()[1:])
        call = int(fields['call']); phase = fields['phase']
        assert phase not in phases.setdefault(call, {})
        phases[call][phase] = float(fields['seconds'])
    elif line.startswith('OpenPLL_wire_PC ') and phases:
        fields = dict(token.split('=', 1) for token in line.split()[1:])
        call = int(fields['call'])
        if call not in phases: continue
        measured = phases.pop(call)
        assert len(measured) == 8 and all(v >= 0 for v in measured.values())
        assert int(fields['status']) == 0 and float(fields['scaled_true_relative_residual']) <= 1e-12
        total = float(fields['seconds'])
        assert sum(measured.values()) <= total
        records.append(dict(call=call, internal_solve_wall_s=total, phase_wall_s=measured,
                            iterations=int(fields['iterations'])))
assert not phases and [r['call'] for r in records] == list(range(1, 9))
aggregates = {name: sum(r['phase_wall_s'][name] for r in records)
              for name in records[0]['phase_wall_s']}
total = sum(r['internal_solve_wall_s'] for r in records)
out = base/'native_solver_stage_profile_review_002'; out.mkdir(exist_ok=False)
pins = {str(p): digest(p) for p in (Path(__file__).resolve(), assessment, header, original, case/'probe.log')}
for name, sha in proof['input_sha256'].items(): assert digest(Path(name)) == sha, name
save(out/'assessment.json', dict(input_sha256=pins, records=records,
     instrumentation_only_source_diff_verified=True, original_equation_and_known_solution_checks=16,
     aggregate_internal_solve_wall_s=total, aggregate_phase_wall_s=aggregates,
     aggregate_phase_fractions={k: v/total for k, v in aggregates.items()},
     instrumented_clocks_and_output_have_unmeasured_overhead=True,
     actual_nonlinear_RHS_sequence_profiled=False, live_DCO_profiled=False,
     full_DCO_speedup_inferred=False, live_simulator_changed=False, release_qualified=False))
print(json.dumps(dict(total_s=total, phase_fractions={k: v/total for k, v in aggregates.items()})))
