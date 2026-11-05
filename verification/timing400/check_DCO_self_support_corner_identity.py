#!/usr/bin/env python3
"""Prove added self-C supports identical across corners before reusing GDS proof.

Compare canonical conductor/material ownership and complete support geometry.
Capacitance coefficients and fringe density multipliers are excluded only from
this geometric identity. Electrical qualification remains separate per corner.
"""
import hashlib
import json
import os
from pathlib import Path
import time
from compile_local_C_operators_v2 import digest, save


def main():
    base = Path(__file__).resolve().parents[2]/'build/timing400/release_001'
    owner = base/'distributed_RC_model_qualification_001/owner.json'
    deadline = json.loads(owner.read_text())['deadline_uptime']
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    out = base/'DCO_self_C_support_corner_identity_001'
    out.mkdir(exist_ok=False)
    proofs = [base/'DCO_self_C_support_transfer_001/assessment.json',
              base/'DCO_self_C_extra_support_GDS_geometry_001/assessment.json']
    assert json.loads(proofs[1].read_text())['all_added_self_extra_supports_covered']
    inputs = [Path(__file__).resolve(), owner, *proofs]
    signatures = {}
    for corner, name in [('nom','DCO_local_C_operators_nom_self_002'),
                         ('min','DCO_local_C_operators_min_self_001'),
                         ('max','DCO_local_C_operators_max_self_001')]:
        folder = base/name
        fields = json.loads((folder/'fields.json').read_text())
        h, count, checked = hashlib.sha256(), 0, 0
        with (folder/'operators.jsonl').open() as stream:
            for checked, text in enumerate(stream,1):
                row = json.loads(text)
                if row[3] < 0:
                    if row[0] == 'A':
                        support = [row[4]]
                    elif row[0] == 'L':
                        support = [row[4],row[5],row[7],row[8]]
                    else:
                        assert row[0] == 'F'
                        support = [row[4],row[5],row[6]]
                    canonical = [row[0],fields[row[1]],fields[row[2]],support]
                    h.update(json.dumps(canonical,separators=(',',':')).encode()+b'\n')
                    count += 1
                if checked % 100000 == 0:
                    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
                    save(out/'status.json',dict(state='comparing_canonical_added_supports',corner=corner,
                        runner_pid=os.getpid(),operators_checked=checked,self_operators=count,deadline_uptime=deadline))
        assert count == 2642914
        signatures[corner] = dict(self_operator_count=count,ordered_canonical_geometry_sha256=h.hexdigest())
        inputs.extend([folder/'fields.json',folder/'operators.jsonl',folder/'assessment.json'])
    matched = signatures['min'] == signatures['nom'] == signatures['max']
    save(out/'assessment.json', dict(all_added_self_support_geometries_identical_across_RC_corners=matched,
        signatures=signatures, nominal_GDS_support_evidence_applies_to_min_and_max=matched,
        capacitance_coefficients_or_electrical_error_qualified=False,
        runtime_model_eligible=False,release_qualified=False,adopted=False,deadline_uptime=deadline,
        input_sha256={str(p.resolve()):digest(p) for p in inputs}))
    save(out/'status.json',dict(state='completed',geometry_identity_passed=matched))
    print(json.dumps(dict(geometry_identity_passed=matched,signatures=signatures),indent=2))


if __name__ == '__main__':
    main()
