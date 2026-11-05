#!/usr/bin/env python3
"""Localize failed max-C modes and compare their unchanged voltages across RC C.

This is a diagnosis. No matrix coefficient, eigenvalue or physical node changes.
"""
from collections import defaultdict
import json
from pathlib import Path
import time
import numpy as np
from scipy.sparse import load_npz
from compile_local_C_operators_v2 import digest, save


def main():
    base = Path(__file__).resolve().parents[2]/'build/timing400/release_001'
    owner = base/'distributed_RC_model_qualification_001/owner.json'
    deadline = json.loads(owner.read_text())['deadline_uptime']
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    out = base/'DCO_max_C_negative_mode_diagnosis_001'
    out.mkdir(exist_ok=False)
    matrices, inputs = {}, [Path(__file__).resolve(), owner]
    names = None
    for corner in ['min', 'nom', 'max']:
        folder = base/f'DCO_local_C_matrix_{corner}_self_001'
        ns = json.loads((folder/'nodes.json').read_text())
        if names is None:
            names = ns
        assert names == ns
        matrices[corner] = load_npz(folder/'C_native_units.npz').tocsr()
        inputs.extend([folder/'nodes.json', folder/'C_native_units.npz', folder/'assessment.json'])
    modes_path = base/'DCO_local_C_matrix_max_self_checks_001/minimum_modes.npz'
    modes = np.load(modes_path)
    node_path = base/'DCO_complete_domain_model_primitives_001/nodes.json'
    plane_path = base/'DCO_direct_native_planes_and_boundaries_001/node_planes.json'
    nodes = {r['private_id']:r for r in json.loads(node_path.read_text())}
    planes = json.loads(plane_path.read_text())
    norms = np.asarray(abs(matrices['max']).sum(axis=1)).ravel()
    results, physical = [], []
    for k, eigenvalue in enumerate(modes['eigenvalues']):
        if eigenvalue >= -1e-9:
            continue
        voltage = np.zeros(len(names))
        active = modes['active_node_indices']
        voltage[active] = modes['vectors'][:, k]/np.sqrt(norms[active])
        voltage /= max(abs(voltage))
        physical.append(voltage)
        energies = {c: float(voltage@matrix@voltage) for c, matrix in matrices.items()}
        assert energies['max'] < 0
        local = voltage*(matrices['max']@voltage)
        groups = defaultdict(float)
        for i, name in enumerate(names):
            group = (nodes.get(name, {}).get('original_conductor', '@REFERENCE'), planes.get(name, 'reference'))
            groups[group] += float(local[i])
        selected = np.argsort(abs(voltage))[-100:][::-1]
        highest = [dict(node=names[i], voltage_V=float(voltage[i]),
                        plane=planes.get(names[i]), geometry=nodes.get(names[i])) for i in selected]
        negative_nodes = np.argsort(local)[:100]
        results.append(dict(mode=int(k), normalized_eigenvalue=float(eigenvalue),
            eigenpair_residual=float(modes['residual_norms'][k]),
            physical_voltage_normalized_to_one_V=True, energy_native_units_by_corner=energies,
            largest_voltage_nodes=highest,
            most_negative_row_energy_nodes=[dict(node=names[i], voltage_V=float(voltage[i]),
                row_energy_native_units=float(local[i]), plane=planes.get(names[i]), geometry=nodes.get(names[i]))
                for i in negative_nodes],
            row_energy_sum_by_conductor_and_plane=[dict(original_conductor=a, plane=b, energy_native_units=e)
                for (a,b),e in sorted(groups.items(), key=lambda item:item[1])]))
    assert len(results) == 2
    np.savez(out/'physical_mode_voltages.npz', voltages=np.asarray(physical))
    save(out/'mode_diagnosis.json', results)
    inputs.extend([modes_path, node_path, plane_path])
    save(out/'assessment.json', dict(maximum_C_matrix_negative_energy_modes_confirmed=len(results),
        energies_native_units=[r['energy_native_units_by_corner'] for r in results],
        coefficients_changed=False, runtime_model_eligible=False, release_qualified=False, adopted=False,
        deadline_uptime=deadline, input_sha256={str(p.resolve()): digest(p) for p in inputs},
        artifacts={str(p.resolve()):digest(p) for p in [out/'physical_mode_voltages.npz', out/'mode_diagnosis.json']}))
    print(json.dumps([dict(mode=r['mode'], energy=r['energy_native_units_by_corner'],
        most_negative_groups=r['row_energy_sum_by_conductor_and_plane'][:6]) for r in results], indent=2))


if __name__ == '__main__':
    main()
