#!/usr/bin/env python3
"""Check restored-bias DC wire residuals without evaluating MOS models or restarting SPICE."""
import json
from pathlib import Path
import re
import numpy as np
from scipy.sparse import coo_matrix
from compile_local_C_operators_v2 import digest, save


def main():
    base = Path(__file__).resolve().parents[2] / 'build/timing400/release_001'
    nodes_path = base / 'DCO_local_C_matrix_nom_no_substrate_G_001/nodes.json'
    bias_path = base / 'DCO_domain_nom_tt27_c0_f247_80ns_canonical_ground_001/initial_bias_canonical_ground.ic'
    devices = base / 'DCO_complete_domain_model_primitives_001/device_connections.json'
    points = base / 'DCO_direct_native_planes_and_boundaries_001/boundary_connections.json'
    rfile = base / 'DCO_domain_R_corners_002/nom_wire_R_unqualified.spice'
    names = json.loads(nodes_path.read_text()); index = {name: i for i, name in enumerate(names)}
    values = {}
    for line in bias_path.read_text().splitlines():
        match = re.fullmatch(r'\.IC V\(([^)]+)\) = (\S+)', line); assert match
        assert match[1].upper() not in values
        values[match[1].upper()] = float(match[2])
    missing = [name for name in names if 'XDCO:XPHYSICAL:' + name.upper() not in values]
    assert missing == ['_dco_substrate_reference'] and names[0] == missing[0]
    values['XDCO:XPHYSICAL:_DCO_SUBSTRATE_REFERENCE'] = 0.
    voltages = np.asarray([values['XDCO:XPHYSICAL:' + name.upper()] for name in names])
    assert np.isfinite(voltages).all()
    protected = {name for row in json.loads(devices.read_text()).values() for name in row['private_terminals']}
    protected.update(row['private_node'] for row in json.loads(points.read_text()))
    protected.add('_dco_substrate_reference')
    rr, cc, vv = [], [], []; count = 0
    for line in rfile.open():
        fields = line.split()
        if not fields or fields[0].startswith('*'): continue
        assert len(fields) == 4 and fields[0].startswith('R')
        a, b = index[fields[1]], index[fields[2]]; g = 1. / float(fields[3])
        assert g > 0 and np.isfinite(g)
        rr.extend([a, b, a, b]); cc.extend([a, b, b, a]); vv.extend([g, g, -g, -g]); count += 1
    assert count == 166286
    G = coo_matrix((vv, (rr, cc)), shape=(len(names), len(names))).tocsr()
    # The missing reference has no resistor incidence, so its assigned voltage
    # cannot affect any residual in this wire-only audit.
    assert G.getrow(0).nnz == 0 and G.getcol(0).nnz == 0
    internal = np.asarray([i for i, name in enumerate(names) if name not in protected])
    residual = (G @ voltages)[internal]
    out = base / 'DCO_saved_bias_wire_KCL_audit_001'; out.mkdir(exist_ok=False)
    paths = [Path(__file__), nodes_path, bias_path, devices, points, rfile]
    result = dict(saved_bias_wire_KCL_checked=True, internal_wire_nodes=len(internal),
        resistor_branches=count, maximum_internal_wire_residual_A=float(max(abs(residual))),
        internal_wire_nodes_above_1nA=int(np.count_nonzero(abs(residual) > 1e-9)),
        intrinsic_BSIM_and_protected_terminal_residuals_evaluated=False,
        full_DCO_initialization_cause_proven=False, full_DCO_speedup_demonstrated=False,
        native_DCO_restarted=False, release_qualified=False, adopted=False,
        input_sha256={str(path.resolve()): digest(path) for path in paths})
    save(out / 'assessment.json', result)
    print(json.dumps({k: v for k, v in result.items() if k != 'input_sha256'}, indent=2))


if __name__ == '__main__':
    main()
