#!/usr/bin/env python3
"""Select exact failing kernel blocks without assuming the negative term kind."""
from collections import Counter
import json
from pathlib import Path
import time

from compile_local_C_operators_v2 import digest, save


def main():
    root = Path(__file__).resolve().parents[2]
    base = root/'build/timing400/release_001'
    owner = base/'distributed_RC_model_qualification_001/owner.json'
    deadline = json.loads(owner.read_text())['deadline_uptime']
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    diagnosis = base/'DCO_negative_C_diagonal_diagnosis_001/assessment.json'
    wanted = set(json.loads(diagnosis.read_text())['source_serials_of_largest_negative_terms'])
    kernels = base/'DCO_C_kernel_trace_controls_001/nom_trace/kernels.log'
    native_path = base/'DCO_C_kernel_trace_controls_001/assessment.json'
    native = json.loads(native_path.read_text())
    source = root/'build/timing400/magic_C_kernel_source_001/extract/ExtCouple.c'
    text = source.read_text()
    assert 'sov.so_coupfrac, sov.so_subfrac, (rtp != rbp) ? 1 : 0' in text
    assert 'rfar != (NodeRegion *) CLIENTDEFAULT && rfar != rinside' in text
    out = base/'DCO_negative_C_kernel_inspection_002'
    out.mkdir(exist_ok=False)
    current, found, matching = [], [], []
    n_kernels = n_events = 0
    def retain():
        if not matching:
            return
        tokens = [s.split() for s in current]
        kind = tokens[0][2]
        rules = [s for s in tokens if s[0] == 'VALUE' and s[2] == 'HALO_RULE_REMAINING']
        self_skip = bool(rules) and all(float(s[6]) == 0 for s in rules)
        found.append(dict(kernel_id=int(tokens[0][1]), kind=kind, matching_event_serials=list(matching),
            same_ideal_conductor_skip_explicit_in_native_flags=self_skip,
            native_pair_event_present=any(s[0] == 'EVENT' and s[2] == 'P' for s in tokens),
            raw_lines=list(current)))
    began = ended = False
    with kernels.open() as stream:
        for textline in stream:
            if textline.startswith('KERNEL '):
                retain()
                current, matching = [textline.rstrip()], []
                n_kernels += 1
                assert int(textline.split()[1]) == n_kernels
                if n_kernels % 100000 == 0:
                    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
                    save(out/'status.json', dict(state='selecting_verified_native_kernel_blocks', kernels_checked=n_kernels, found=len(found)))
            elif textline.startswith('EVENT '):
                n_events += 1
                event = int(textline.split()[1])
                assert event == n_events
                if event in wanted:
                    matching.append(event)
                current.append(textline.rstrip())
            elif textline.startswith('BEGIN '):
                assert not began
                began = True
            elif textline.startswith('END '):
                assert textline.split() == ['END', str(n_events), str(n_kernels)]
                retain()
                current, matching = [], []
                ended = True
            else:
                assert current and textline.startswith(('RECT ', 'VALUE '))
                current.append(textline.rstrip())
    assert began and ended and n_kernels == 7421041 and n_events == 8297230
    assert wanted == {n for r in found for n in r['matching_event_serials']}
    assert digest(kernels) == native['artifacts'][str(kernels.resolve())]
    save(out/'selected_kernels.json', found)
    result = dict(selected_largest_negative_ground_events=len(wanted),
        selected_kernel_kinds=dict(Counter(r['kind'] for r in found)),
        explicit_same_ideal_conductor_skipped_pair_kernels=sum(r['same_ideal_conductor_skip_explicit_in_native_flags'] for r in found),
        actual_source_kind_assumption_in_previous_reader_rejected=True,
        previous_reader_failure='Assertion assumed every negative term was FRINGE_HALO; actual terms also include BLOCKED_FRINGE.',
        exact_selected_blocks_from_previously_verified_native_trace=True,
        candidate_fix_hypothesis='Restore geometrically owned intra-conductor overlap, fringe, and sidewall coupling before rechecking passivity.',
        restored_self_coupling_sufficiency_proven=False,
        runtime_model_eligible=False, release_qualified=False, adopted=False, deadline_uptime=deadline,
        input_sha256={str(p.resolve()): digest(p) for p in [Path(__file__).resolve(), owner, diagnosis, kernels, source, native_path]},
        artifacts={str((out/'selected_kernels.json').resolve()): digest(out/'selected_kernels.json')})
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    save(out/'assessment.json', result)
    save(out/'status.json', dict(state='completed'))
    print(json.dumps({k: v for k, v in result.items() if k not in ['input_sha256', 'artifacts']}, indent=2))


if __name__ == '__main__':
    main()
