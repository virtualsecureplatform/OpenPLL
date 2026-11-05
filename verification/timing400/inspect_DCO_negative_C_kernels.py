#!/usr/bin/env python3
"""Inspect native self-conductor skips behind the measured negative diagonal."""
import json
from pathlib import Path
import time
from compile_local_C_operators_v2 import digest, save
from verify_magic_C_kernel_trace_v2 import blocks


def main():
    root = Path(__file__).resolve().parents[2]
    base = root/'build/timing400/release_001'
    owner = base/'distributed_RC_model_qualification_001/owner.json'
    deadline = json.loads(owner.read_text())['deadline_uptime']
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    diagnosis = base/'DCO_negative_C_diagonal_diagnosis_001/assessment.json'
    wanted = set(json.loads(diagnosis.read_text())['source_serials_of_largest_negative_terms'])
    kernels = base/'DCO_C_kernel_trace_controls_001/nom_trace/kernels.log'
    source = root/'build/timing400/magic_C_kernel_source_001/extract/ExtCouple.c'
    source_text = source.read_text()
    assert 'sov.so_coupfrac, sov.so_subfrac, (rtp != rbp) ? 1 : 0' in source_text
    assert 'if (rtp == rbp) return 0;' in source_text
    out = base/'DCO_negative_C_kernel_inspection_001'
    out.mkdir(exist_ok=False)
    found = []
    for count, block in enumerate(blocks(kernels), 1):
        if count % 10000 == 0:
            assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
            save(out/'status.json', dict(state='inspecting_selected_native_kernels', kernels_checked=count, found=len(found)))
        matching = [r for r in block['events'] if int(r[1]) in wanted]
        if matching:
            rows = block['values'].get('HALO_RULE_REMAINING', [])
            self_skip = bool(rows) and all(v[2] == 0 for _, v in rows)
            assert block['kind'] == 'FRINGE_HALO'
            found.append(dict(matching_event_serials=[int(r[1]) for r in matching],
                all_rules_native_same_ideal_conductor=True if self_skip else False,
                native_pair_event_present=any(r[2] == 'P' for r in block['events']), kernel=block))
    assert wanted == {n for r in found for n in r['matching_event_serials']}
    save(out/'selected_kernels.json', found)
    result = dict(selected_largest_negative_ground_events=len(wanted),
        same_ideal_conductor_skipped_pair_kernels=sum(r['all_rules_native_same_ideal_conductor'] for r in found),
        distinct_conductor_kernels=sum(not r['all_rules_native_same_ideal_conductor'] for r in found),
        full_C_energy_assignment_rejected=True,
        candidate_fix_hypothesis='Restore geometrically owned intra-conductor coupling for finite-R voltage differences before evaluating passivity again.',
        restored_self_coupling_sufficiency_proven=False,
        runtime_model_eligible=False, release_qualified=False, adopted=False,
        deadline_uptime=deadline,
        input_sha256={str(p.resolve()): digest(p) for p in [Path(__file__).resolve(), owner, diagnosis, kernels, source]},
        artifacts={str((out/'selected_kernels.json').resolve()): digest(out/'selected_kernels.json')})
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    save(out/'assessment.json', result)
    save(out/'status.json', dict(state='completed'))
    print(json.dumps({k: v for k, v in result.items() if k not in ['input_sha256', 'artifacts']}, indent=2))


if __name__ == '__main__':
    main()
