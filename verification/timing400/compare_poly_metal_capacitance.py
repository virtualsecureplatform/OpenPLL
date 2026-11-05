#!/usr/bin/env python3
"""Compare terminal metal-only and poly+metal extraction experiments.

Check complete native device statements, not just transistor counts. Report
parent matrix-diagonal changes without treating them as effective timing loads.
The expanded network replaces the prior view; it is not an additive C patch.
"""
from collections import Counter
import json
import math
from pathlib import Path
import signal
import time
from check_compact_clock_tree import verify
from run_dco_qualification import ROOT, sha, save


def devices(path):
    rows = Counter()
    with path.open() as stream:
        for line in stream:
            if line.startswith('device '):
                rows[' '.join(line.split())]+=1
    assert rows
    return rows


def main():
    base = ROOT/'build/timing400/release_001'
    old = base/'parent_filled_metal_capacitance_extract_002'
    new = base/'parent_filled_poly_metal_capacitance_extract_003'
    out = base/'poly_metal_capacitance_comparison_001'
    owner = json.loads((new/'owner.json').read_text())
    left = owner['deadline_uptime']-time.clock_gettime(time.CLOCK_BOOTTIME)
    assert left>0
    signal.alarm(max(1,math.floor(left)))
    paths = [Path(__file__).resolve(),new/'owner.json']
    for directory in [old,new]:
        receipt = verify(directory/'native_completion.json')
        assert receipt['native_extraction_completed']
        paths += [directory/'native_completion.json',directory/'IntegerPLL_400MHz_FilledCapView.ext']
    old_devices,new_devices = [devices(p/'IntegerPLL_400MHz_FilledCapView.ext') for p in [old,new]]
    removed,added = old_devices-new_devices,new_devices-old_devices
    counts_equal = sum(old_devices.values())==sum(new_devices.values())
    full_statements_equal = not removed and not added
    audits = [base/'parent_filled_metal_capacitance_network_audit_001',
        base/'parent_filled_poly_metal_capacitance_network_audit_001']
    nodes = []
    for directory in audits:
        verify(directory/'assessment.json')
        paths += [directory/'assessment.json',directory/'parent_nodes.json']
        nodes.append({r['parent_node']:r for r in json.loads((directory/'parent_nodes.json').read_text())})
    assert nodes[0].keys()==nodes[1].keys() and len(nodes[0])==359
    deltas = []
    for name,a in nodes[0].items():
        b = nodes[1][name]
        before,after = a['positive_diagonal_f'],b['positive_diagonal_f']
        assert before>0 and after>0
        deltas.append(dict(parent_node=name,metal_only_positive_diagonal_f=before,
            poly_metal_positive_diagonal_f=after,change_f=after-before,change_fraction=(after-before)/before))
    # These fault controls concern real parsed device data, without rerunning
    # extraction or modifying a source. Removing a device must break equality.
    corrupted = new_devices.copy()
    corrupted[next(iter(corrupted))]-=1
    assert corrupted!=old_devices
    out.mkdir(exist_ok=False)
    save(out/'parent_deltas.json',deltas)
    save(out/'device_statement_differences.json',dict(removed=dict(removed),added=dict(added)))
    save(out/'assessment.json',dict(input_sha256={str(p):sha(p) for p in paths},
        artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file()},
        old_native_device_statements=sum(old_devices.values()),new_native_device_statements=sum(new_devices.values()),
        device_counts_equal=counts_equal,all_native_device_statements_preserved=full_statements_equal,
        removed_device_statement_count=sum(removed.values()),added_device_statement_count=sum(added.values()),
        missing_device_negative_control_rejected=True,parent_node_comparisons=359,
        replacement_network_not_additive_capacitance_patch=True,
        deltas_are_effective_load_changes=False,full_fom_substrate_coverage_qualified=False,
        full_rc_enclosure_qualified=False,physical_timing_qualified=False,
        release_qualified=False,adopted=False,scope=__doc__))
    print('Device statements preserved:',full_statements_equal,'; compared359 parent diagonals; effective loading unqualified.')


if __name__=='__main__':
    main()
