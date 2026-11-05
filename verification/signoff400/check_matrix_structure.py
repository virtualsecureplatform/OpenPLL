"""Control compiled charge conservation and necessary principal-minor checks."""
import argparse
import json
from fractions import Fraction
from pathlib import Path
import shutil
import time
from common import ROOT, save, sha
from compiled_charge import execute
from resources import lease


def run(output):
    out = output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    deadline = time.clock_gettime(time.CLOCK_BOOTTIME) + 3600
    source = ROOT/'tools/sheet_charge'
    compiler = Path(shutil.which('g++')).resolve()
    paths = [Path(__file__).resolve(), compiler, ROOT/'tools/charge_compiler/json.hpp',
             *[source/p for p in ('audit_sparse_matrix.cpp', 'matrix_structure_fixtures.cpp',
                                 'sparse_run_slice.hpp', 'sparse_runs_v2.hpp')]]
    pins = {str(p): sha(p) for p in paths}
    cases = [('positive', 4, True), ('positive', 5, True),
             ('negative_diagonal', 2, False), ('negative_minor', 3, False),
             ('zero_diagonal_coupling', 3, False), ('gauge_error', 4, False),
             ('higher_order_indefinite', 4, True)]
    reports = []
    with lease(8, 8, deadline):
        for name in ('audit_sparse_matrix', 'matrix_structure_fixtures'):
            execute([compiler, '-std=c++20', '-O3', '-fopenmp', '-Wall', '-Wextra',
                     '-Wpedantic', '-fno-fast-math', '-ffp-contract=off',
                     source/(name+'.cpp'), '-o', out/name], out/(name+'.build.log'), deadline, 8)
        execute([out/'matrix_structure_fixtures', out], out/'fixtures.log', deadline, 1)
        for name, nodes, expected in cases:
            for threads in (1, 4, 8):
                label = f'{name}_{nodes}_{threads}'
                cfg, report = out/(label+'.json'), out/(label+'.report.json')
                save(cfg, dict(matrix=str(out/(name+'.bin')), node_count=nodes, threads=threads,
                               maximum_dense_bytes=8*1024**3, deadline_uptime=deadline,
                               scaled_charge_residual_limit=1e-12, report=str(report)))
                execute([out/'audit_sparse_matrix', cfg], out/(label+'.log'), deadline, 8)
                value = json.loads(report.read_text())
                assert value['necessary_checks_pass'] == expected, label
                assert not value['full_matrix_passivity_verified'], label
                assert not value['physical_RC_qualified'] and not value['release_qualified'], label
                if name == 'positive':
                    assert value['zero_coefficient_rows'] == nodes-4
                if name == 'negative_diagonal':
                    assert value['significant_negative_diagonal_records'] == 2
                if name in ('negative_minor', 'zero_diagonal_coupling'):
                    assert value['significant_negative_two_by_two_minors'] > 0
                if name == 'zero_diagonal_coupling':
                    assert value['significant_negative_diagonal_records'] == 0
                if name == 'gauge_error':
                    assert not value['charge_conservation_within_limit']
                reports.append(report)
        # Independent exact negative-energy witness that passes every 2x2 test.
        matrix = [[255, -415, -85, 245], [-415, 695, -195, -85],
                  [-85, -195, 695, -415], [245, -85, -415, 255]]
        vector = [0, 2, 4, 6]
        energy = sum(Fraction(matrix[i][j], 1000)*vector[i]*vector[j]
                     for i in range(4) for j in range(4))
        assert energy == -2
        assert all(sum(row) == 0 for row in matrix)
        assert all(matrix[i][i]*matrix[j][j]-matrix[i][j]**2 > 0
                   for i in range(4) for j in range(i+1, 4))
        if any(sha(Path(p)) != h for p, h in pins.items()):
            raise ValueError('matrix structure control input changed')
        products = [out/'audit_sparse_matrix', out/'matrix_structure_fixtures',
                    *out.glob('*.bin'), *reports]
        save(out/'assessment.json', dict(input_sha256=pins,
             artifacts={str(p): sha(p) for p in products}, matrix_structure_controls_pass=True,
             control_runs=len(reports), thread_counts=[1, 4, 8],
             higher_order_negative_energy_exact=str(energy),
             necessary_checks_explicitly_insufficient_for_PSD=True,
             full_matrix_passivity_verified=False, physical_RC_qualified=False,
             release_qualified=False))
        print(json.dumps(dict(matrix_structure_controls_pass=True, control_runs=len(reports))))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args().output)
