#!/usr/bin/env python3
"""Compare passive-block symbolic fill without running or changing SPICE.

Patterns omit nonlinear-device Jacobians, internal BSIM unknowns and point-source
MNA rows. These are diagnostic estimates, never full native runtime predictions.
"""
import argparse
import json
from pathlib import Path
import subprocess
import time
import numpy as np
from scipy.sparse import coo_matrix, eye, load_npz
from compile_local_C_operators_v2 import digest, save


def pattern(matrix):
    result = matrix.copy().tocsc()
    result.eliminate_zeros()
    result.data = np.ones(result.nnz, dtype=np.int8)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    base = root / 'build/timing400/release_001'
    owner = base / 'distributed_RC_model_qualification_001/owner.json'
    deadline = json.loads(owner.read_text())['deadline_uptime']
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    helper = root / 'build/timing400/stock_KLU_pattern_tools_001/analyze_stock_KLU_pattern'
    inputs = [Path(__file__).resolve(), Path(__file__).with_name('analyze_stock_KLU_pattern.c'),
              helper, owner, Path('/opt/trilinos/lib/libamesos.a'),
              Path('/opt/trilinos/include/trilinos_klu_decl.h')]
    args.output.mkdir(exist_ok=False)
    nodes_path = base / 'DCO_local_C_matrix_nom_self_001/nodes.json'
    nodes = json.loads(nodes_path.read_text())
    assert nodes[0] == '_dco_substrate_reference'
    indices = {name: i for i, name in enumerate(nodes)}
    branches = base / 'DCO_complete_domain_model_primitives_001/branches.jsonl'
    rows, columns = [], []
    for line in branches.open():
        a, b = json.loads(line)['private_nodes']
        rows.extend([indices[a], indices[b]])
        columns.extend([indices[b], indices[a]])
    resistor_graph = coo_matrix((np.ones(len(rows), dtype=np.int8), (rows, columns)),
                               shape=(len(nodes), len(nodes))).tocsc()
    inputs.extend([nodes_path, branches])
    results = {}
    def analyze(name, graph):
        graph = pattern(graph + eye(graph.shape[0], dtype=np.int8, format='csc'))
        graph.sort_indices()
        assert graph.nnz < np.iinfo(np.int32).max
        path = args.output / (name + '.csc')
        with path.open('xb') as stream:
            np.asarray([graph.shape[0], graph.nnz], dtype=np.int32).tofile(stream)
            graph.indptr.astype(np.int32).tofile(stream)
            graph.indices.astype(np.int32).tofile(stream)
        start = time.monotonic()
        completed = subprocess.run([str(helper), str(path)], capture_output=True, text=True,
            timeout=min(90, deadline - time.clock_gettime(time.CLOCK_BOOTTIME)))
        assert completed.returncode == 0, completed.stderr
        result = json.loads(completed.stdout)
        result['elapsed_s'] = time.monotonic() - start
        results[name] = result
        save(args.output / (name + '.json'), result)
        print(name, json.dumps(result), flush=True)
    for name, folder in [('original_C', 'DCO_local_C_matrix_nom_self_001'),
                         ('corrected_C', 'DCO_local_C_matrix_nom_no_substrate_G_001')]:
        directory = base / folder
        assert json.loads((directory / 'nodes.json').read_text()) == nodes
        matrix_path = directory / 'C_native_units.npz'
        graph = pattern(load_npz(matrix_path)) + resistor_graph
        inputs.extend([matrix_path, directory / 'nodes.json'])
        if name == 'original_C':
            analyze(name + '_named_reference', graph)
        analyze(name + '_grounded_reference', graph[1:, 1:])
    prototype = base / 'DCO_passive_path_condensation_nom_1fs_001'
    proto_nodes = json.loads((prototype / 'nodes.json').read_text())
    assert proto_nodes[0] == '_dco_substrate_reference'
    paths = [prototype / 'C_native_units.npz', prototype / 'G_S.npz']
    inputs.extend(paths + [prototype / 'nodes.json'])
    graph = pattern(load_npz(paths[0])) + pattern(load_npz(paths[1]))
    analyze('isolated_path_prototype_grounded_reference', graph[1:, 1:])
    save(args.output / 'assessment.json', dict(stock_KLU_symbolic_pattern_comparison_completed=True,
        results=results, passive_block_patterns_only=True,
        nonlinear_device_and_MNA_patterns_included=False,
        native_transient_runtime_prediction_qualified=False,
        engine_or_library_modified=False, active_circuit_or_solver_changed=False,
        physical_model_or_frequency_error_qualified=False,
        runtime_model_eligible=False, release_qualified=False, adopted=False,
        deadline_uptime=deadline, input_sha256={str(p.resolve()): digest(p) for p in inputs},
        artifacts={str(p.resolve()): digest(p) for p in args.output.iterdir() if p.suffix in ['.csc', '.json']}))


if __name__ == '__main__':
    main()
