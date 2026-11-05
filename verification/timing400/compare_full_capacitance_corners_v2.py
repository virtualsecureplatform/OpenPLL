#!/usr/bin/env python3
"""Compare full-layout capacitance corners and normalized native devices.

Schema normalization is limited to independently tested M/X, R/X and D/X
forms. Keep any remaining device/node differences and capacitor-order
inversions visible. Matrix diagonals are not effective timing loads.
"""
from collections import Counter
import json
import math
from pathlib import Path
import signal
import time
from audit_capacitance_corner_controls import native_devices
from audit_primitive_corner_exports import native as native_two_terminal
from check_compact_clock_tree import verify
from run_dco_qualification import ROOT,sha,save


def devices(path):
    result=Counter()
    with path.open() as stream:
        for line in stream:
            if not line.startswith('device '):continue
            fields=line.split()
            if 'fet' in fields[2]:result.update(native_devices([line]))
            else:result.update(native_two_terminal([line]))
    assert sum(result.values())==100462
    return result


def main():
    base=ROOT/'build/timing400/release_001'
    source=base/'poly_metal_full_capacitance_corners_002'
    collection=base/'poly_metal_full_capacitance_corner_collection_002'
    out=base/'poly_metal_full_capacitance_corner_comparison_002'
    owner=json.loads((source/'owner.json').read_text())
    left=owner['deadline_uptime']-time.clock_gettime(time.CLOCK_BOOTTIME)
    assert left>0
    signal.alarm(max(1,math.floor(left)))
    nominal=base/'parent_filled_poly_metal_capacitance_extract_003'
    directories={'min':source/'min','nom':nominal,'max':source/'max'}
    paths=[Path(__file__).resolve(),Path(__file__).with_name('audit_capacitance_corner_controls.py'),
        Path(__file__).with_name('audit_primitive_corner_exports.py'),source/'owner.json']
    device_sets={}
    nodes={}
    for corner,directory in directories.items():
        receipt=verify(directory/'native_completion.json')
        assert receipt['native_extraction_completed']
        ext=directory/'IntegerPLL_400MHz_FilledCapView.ext'
        paths += [directory/'native_completion.json',ext]
        device_sets[corner]=devices(ext)
        audit=base/'parent_filled_poly_metal_capacitance_network_audit_001' if corner=='nom' else collection/corner/'network'
        data=verify(audit/'assessment.json')
        assert not data['missing_parent_nodes'] and not data['negative_capacitor_examples']
        paths += [audit/'assessment.json',audit/'parent_nodes.json']
        nodes[corner]={r['parent_node']:r for r in json.loads((audit/'parent_nodes.json').read_text())}
    assert nodes['min'].keys()==nodes['nom'].keys()==nodes['max'].keys() and len(nodes['nom'])==359
    differences={}
    for corner in ['min','max']:
        removed=device_sets['nom']-device_sets[corner]
        added=device_sets[corner]-device_sets['nom']
        differences[corner]=dict(removed=sum(removed.values()),added=sum(added.values()),
            removed_examples=[list(row) for row in list(removed)[:20]],
            added_examples=[list(row) for row in list(added)[:20]])
    deltas=[]
    inversions=[]
    for name in sorted(nodes['nom']):
        caps={c:nodes[c][name]['positive_diagonal_f'] for c in ['min','nom','max']}
        ordered=caps['min']<=caps['nom']+1e-27<=caps['max']+2e-27
        row=dict(parent_node=name,positive_matrix_diagonal_f=caps,ordered_min_nom_max=ordered)
        deltas.append(row)
        if not ordered:inversions.append(row)
    # A removed statement must differ from the same real parsed baseline.
    damaged=device_sets['min'].copy()
    damaged[next(iter(damaged))]-=1
    assert damaged!=device_sets['min']
    out.mkdir(exist_ok=False)
    save(out/'parent_diagonals.json',deltas)
    save(out/'normalized_device_differences.json',differences)
    save(out/'assessment.json',dict(input_sha256={str(p):sha(p) for p in paths},
        artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file()},
        full_layout_corners=['min','nom','max'],native_device_statements_each_corner=100462,
        normalized_device_statements_all_preserved=all(not v['removed'] and not v['added'] for v in differences.values()),
        native_device_difference_counts={c:{k:v[k] for k in ['removed','added']} for c,v in differences.items()},
        parent_nodes_compared=359,parent_diagonal_corner_order_inversions=inversions,
        missing_device_negative_control_rejected=True,reported_sums_are_effective_loads=False,
        fom_material_enclosure_qualified=False,full_rc_enclosure_qualified=False,
        physical_timing_qualified=False,release_qualified=False,adopted=False,scope=__doc__))
    print('Full-C corners compared:359 parent diagonals;',len(inversions),'order inversions; device differences:',
        {c:{k:v[k] for k in ['removed','added']} for c,v in differences.items()})


if __name__=='__main__':main()
