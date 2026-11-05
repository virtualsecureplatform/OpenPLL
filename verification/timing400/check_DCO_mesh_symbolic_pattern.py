#!/usr/bin/env python3
"""Measure isolated mesh-projection passive fill with stock symbolic KLU."""
import argparse
import json
from pathlib import Path
import subprocess
import time
import numpy as np
from scipy.sparse import eye, load_npz
from check_DCO_stock_symbolic_patterns_v2 import pattern
from compile_local_C_operators_v2 import digest, save


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--matrix', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    base = root / 'build/timing400/release_001'
    owner = base / 'distributed_RC_model_qualification_001/owner.json'
    deadline = json.loads(owner.read_text())['deadline_uptime']
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    proof_path = args.matrix / 'assessment.json'
    proof = json.loads(proof_path.read_text())
    assert proof['passive_mesh_condensation_prototype_built']
    assert proof['all_protected_vertices_retained'] and proof['all_equivalent_R_positive']
    names = json.loads((args.matrix / 'nodes.json').read_text())
    assert names[0] == '_dco_substrate_reference'
    C, G = [load_npz(args.matrix / filename) for filename in ['C_native_units.npz', 'G_S.npz']]
    graph = pattern(pattern(C) + pattern(G) + eye(len(names), dtype=np.int8, format='csc'))[1:, 1:].tocsc()
    graph.sort_indices()
    args.output.mkdir(exist_ok=False)
    csc = args.output / 'grounded_pattern.csc'
    with csc.open('xb') as stream:
        np.asarray([graph.shape[0], graph.nnz], dtype=np.int32).tofile(stream)
        graph.indptr.astype(np.int32).tofile(stream); graph.indices.astype(np.int32).tofile(stream)
    helper = root / 'build/timing400/stock_KLU_pattern_tools_001/analyze_stock_KLU_pattern'
    start = time.monotonic()
    completed = subprocess.run([str(helper), str(csc)], capture_output=True, text=True,
        timeout=min(90, deadline - time.clock_gettime(time.CLOCK_BOOTTIME)))
    assert completed.returncode == 0, completed.stderr
    metrics = json.loads(completed.stdout)
    reference_path = base / 'DCO_stock_symbolic_pattern_comparison_002/assessment.json'
    reference = json.loads(reference_path.read_text())['results']['corrected_C_grounded_reference']
    inputs = [Path(__file__).resolve(), Path(__file__).with_name('check_DCO_stock_symbolic_patterns_v2.py'),
        owner, proof_path, helper, reference_path, args.matrix / 'nodes.json',
        args.matrix / 'C_native_units.npz', args.matrix / 'G_S.npz']
    result = dict(passive_mesh_symbolic_pattern_checked=True, metrics=metrics,
        comparison_full_grounded_metrics=reference,
        estimated_flops_ratio=metrics['estimated_flops'] / reference['estimated_flops'],
        estimated_L_nnz_ratio=metrics['estimated_L_nnz'] / reference['estimated_L_nnz'],
        elapsed_s=time.monotonic() - start, nonlinear_device_and_MNA_patterns_included=False,
        native_runtime_or_frequency_error_qualified=False, active_model_changed=False,
        release_qualified=False, adopted=False, deadline_uptime=deadline,
        input_sha256={str(path.resolve()): digest(path) for path in inputs},
        artifacts={str(csc.resolve()): digest(csc)})
    save(args.output / 'assessment.json', result)
    print(json.dumps({key: value for key, value in result.items() if key not in ['input_sha256', 'artifacts']}))


if __name__ == '__main__': main()
