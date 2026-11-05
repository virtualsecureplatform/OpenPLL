#!/usr/bin/env python3
"""Export a checked signed C matrix and complete R/MOS family for diagnostics.

The 311-port physical subcircuit keeps both supply-layer point feeds and the
substrate reference explicit. A separately named 308-port ideal-feed wrapper
supports the existing DCO testbench. Neither interface is release qualified.
"""
import argparse
import json
from pathlib import Path
import time
import numpy as np
from scipy.sparse import load_npz

from compile_local_C_operators_v2 import digest, save


def header(name, ports):
    lines = ['.subckt '+name]
    for offset in range(0, len(ports), 8):
        lines.append('+ '+' '.join(ports[offset:offset+8]))
    return '\n'.join(lines)+'\n'


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--matrix', required=True, type=Path)
    p.add_argument('--matrix-check', required=True, type=Path)
    p.add_argument('--corner', choices=['min', 'nom', 'max'], required=True)
    p.add_argument('--output', required=True, type=Path)
    args = p.parse_args()
    root = Path(__file__).resolve().parents[2]
    base = root/'build/timing400/release_001'
    owner = base/'distributed_RC_model_qualification_001/owner.json'
    deadline = json.loads(owner.read_text())['deadline_uptime']
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    check = json.loads(args.matrix_check.read_text())
    assert check['zero_wire_R_collapse_matches_owned_physical_operator_totals']
    assert check['signed_global_passivity_numerical_check_passed']
    matrix_path = args.matrix/'C_native_units.npz'
    assert check['input_sha256'][str(matrix_path.resolve())] == digest(matrix_path)
    proof = json.loads((args.matrix/'assessment.json').read_text())
    if args.corner == 'nom':
        assert proof['full_nominal_C_energy_matrix_assembled']
    else:
        assert proof['full_C_energy_matrix_assembled'] and proof['RC_corner'] == args.corner
    family = base/'DCO_complete_domain_model_primitives_001'
    direct = base/'DCO_direct_native_planes_and_boundaries_001'
    rvalues = base/'DCO_domain_R_corners_002'
    assert json.loads((rvalues/'assessment.json').read_text())['all166286_nominal_values_reproduce_native_float32_formulas_exactly']
    assert json.loads((base/'DCO_contact_cut_count_geometry_001/assessment.json').read_text())['all35578_native_contact_branch_cut_counts_match_actual_GDS']
    matrix = load_npz(matrix_path).tocsr()
    nodes = json.loads((args.matrix/'nodes.json').read_text())
    assert nodes[0] == '_dco_substrate_reference' and matrix.shape == (len(nodes), len(nodes))
    interfaces = json.loads((direct/'boundary_connections.json').read_text())
    ports = sorted(set(r['physical_boundary'] for r in interfaces))
    public = sorted(set(r['public_port'] for r in interfaces))
    assert len(ports) == 310 and len(public) == 308
    logical = {}
    for r in interfaces:
        assert logical.get(r['physical_boundary'], r['public_port']) == r['public_port']
        logical[r['physical_boundary']] = r['public_port']
    name = 'OpenPLL_DCO_domain_'+args.corner
    args.output.mkdir(exist_ok=False)
    deck = args.output/'candidate_unqualified.spice'
    positive = negative = 0
    reconstructed_diagonal = np.zeros(len(nodes))
    with deck.open('x') as stream:
        stream.write('* Diagnostic candidate. Full runtime and physical integration qualification remain open.\n')
        stream.write(header(name, ports+['_dco_substrate_reference']))
        for component in [rvalues/(args.corner+'_wire_R_unqualified.spice'), family/'devices_unqualified.spice', direct/'point_connections_unqualified.spice']:
            stream.write(component.read_text())
        serial = 0
        for a in range(matrix.shape[0]):
            for k in range(matrix.indptr[a], matrix.indptr[a+1]):
                b = matrix.indices[k]
                if b <= a or not matrix.data[k]:
                    continue
                native = -matrix.data[k]
                text = format(native*1e-18, '.17g')
                recovered = float(text)/1e-18
                assert abs(recovered-native) <= 3e-16*abs(native)
                reconstructed_diagonal[a] += recovered
                reconstructed_diagonal[b] += recovered
                serial += 1
                positive += int(native > 0)
                negative += int(native < 0)
                stream.write(f'CFIELD_{serial} {nodes[a]} {nodes[b]} {text}\n')
            if a % 1000 == 0:
                assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
        stream.write('.ends '+name+'\n')
        wrapper = name+'__ideal_point_feeds'
        stream.write('* Explicit diagnostic assumption: both PG layer points share ideal public supply, substrate reference is VGND.\n')
        stream.write(header(wrapper, public))
        stream.write('Xphysical\n')
        connections = [logical[port] for port in ports]+['VGND', name]
        for offset in range(0, len(connections), 8):
            stream.write('+ '+' '.join(connections[offset:offset+8])+'\n')
        stream.write('.ends '+wrapper+'\n')
    row_scale = np.asarray(abs(matrix).sum(axis=1)).ravel()
    residual = abs(reconstructed_diagonal-matrix.diagonal())/np.maximum(row_scale, 1e-30)
    assert max(residual) < 1e-11
    inputs = [Path(__file__).resolve(), owner, args.matrix_check, args.matrix/'assessment.json', matrix_path,
        args.matrix/'nodes.json', family/'devices_unqualified.spice', direct/'point_connections_unqualified.spice',
        direct/'boundary_connections.json', rvalues/(args.corner+'_wire_R_unqualified.spice'),
        rvalues/'assessment.json', base/'DCO_contact_cut_count_geometry_001/assessment.json',
        base/'signed_C_Xyce_controls_002/assessment.json']
    save(args.output/'assessment.json', dict(signed_matrix_branch_realization_readback_passed=True,
        source_matrix_numerical_passivity_check_passed=True, physical_ports=311, public_diagnostic_wrapper_ports=308,
        physical_subcircuit=name, diagnostic_wrapper=wrapper, RC_corner=args.corner,
        public_port_names=public, physical_port_names=ports, substrate_reference_port='_dco_substrate_reference',
        capacitor_branches=serial, positive_scalar_branches=positive, negative_scalar_branches=negative,
        maximum_relative_diagonal_readback_residual=float(max(residual)), finite_R_branches=166286, native_devices=8620,
        assumptions=['Independent ideal voltage at both physical PG layer point feeds', 'Implicit substrate reference fixed to external VGND',
            'Signal ports use the recorded native source point; full parent feed/load integration remains open'],
        actual_DCO_transient_accuracy_or_full_physical_integration_qualified=False,
        runtime_model_eligible=False, release_qualified=False, adopted=False, deadline_uptime=deadline,
        input_sha256={str(f.resolve()): digest(f) for f in inputs}, artifacts={str(deck.resolve()): digest(deck)}))


if __name__ == '__main__':
    main()
