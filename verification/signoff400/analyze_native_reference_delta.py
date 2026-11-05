"""Quantify native-output versus physical-integral reference differences."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import shutil
import time
from common import ROOT, save, sha
from compiled_charge import execute
from resources import lease


def run(reference, controls, output):
    reference, controls, out = (p.resolve() for p in (reference, controls, output))
    out.mkdir(parents=True, exist_ok=False)
    deadline = time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    receipt, proof = reference/'assessment.json', controls/'assessment.json'
    r, c = (json.loads(p.read_text()) for p in (receipt, proof))
    if not r['native_capacitor_scalar_matrix_references_prepared'] or not c['capacitor_scalar_expansion_controls_pass']:
        raise ValueError('complete references and scalar-expansion controls required')
    if r['input_sha256'].get(str(proof)) != sha(proof):
        raise ValueError('reference/control lineage differs')
    left, right = Path(r['physical_integral_reference_matrix']), Path(r['native_output_reference_matrix'])
    test_left, test_right = (controls/'threads_1'/name for name in ('physical.bin', 'native.bin'))
    source = ROOT/'tools/sheet_charge/compare_sparse_matrices.cpp'
    compiler = Path(shutil.which('g++')).resolve()
    paths = [receipt, proof, left, right, test_left, test_right, source, compiler,
             source.with_name('sparse_runs_v2.hpp'), ROOT/'tools/charge_compiler/json.hpp', Path(__file__).resolve()]
    with lease(2, 4, deadline):
        with ThreadPoolExecutor(max_workers=8) as pool:
            pins = dict(zip(map(str, paths), pool.map(sha, paths)))
        if any(pins[str(p)] != r['artifacts'][str(p)] for p in (left, right)):
            raise ValueError('native reference matrices changed')
        binary = out/'compare_sparse_matrices'
        execute([compiler, '-std=c++20', '-O3', '-Wall', '-Wextra', '-Wpedantic',
                 '-fno-fast-math', '-ffp-contract=off', source, '-o', binary], out/'build.log', deadline, 2)
        def compare(name, a, b, count, require):
            cfg = out/(name+'.json')
            result = out/(name+'.report.json')
            save(cfg, dict(left=str(a), right=str(b), node_count=count, absolute_tolerance=1e-8,
                 relative_tolerance=2e-12, require_match=require, report=str(result), deadline_uptime=deadline))
            execute([binary, cfg], out/(name+'.log'), deadline, 2)
            return json.loads(result.read_text())
        same = compare('same_control', test_left, test_left, 3, True)
        changed = compare('changed_control', test_left, test_right, 3, False)
        if not same['within_tolerance'] or same['maximum_absolute_delta'] != 0:
            raise ValueError('matrix comparator rejects an identical matrix')
        if changed['within_tolerance'] or changed['outside_tolerance_entries'] != 3 or changed['maximum_absolute_delta'] != 3:
            raise ValueError('matrix comparator misses the known clamp-only control delta')
        if changed['categories']['diagonal']['signed_delta_sum'] != 6 or changed['categories']['reference_edge']['signed_delta_sum'] != -3:
            raise ValueError('matrix comparator delta categories or signs differ')
        save(out/'status.json', dict(state='streaming_full_native_reference_difference', release_qualified=False))
        result = compare('native_reference_delta', left, right, r['conductor_nets'], False)
        with ThreadPoolExecutor(max_workers=8) as pool:
            if list(pool.map(sha, paths)) != list(pins.values()):
                raise ValueError('native reference delta input changed')
        products = [binary, *sorted(out.glob('*.report.json')), *sorted(out.glob('*.log'))]
        save(out/'assessment.json', dict(input_sha256=pins, artifacts={str(p): sha(p) for p in products},
             matrix_comparator_identity_and_clamp_controls_pass=True,
             native_output_vs_physical_reference_differences_quantified=True,
             full_reference_comparison=result, diagnostic_only=True,
             coefficient_units='retained_native_capacitance_units',
             comparison_with_full_spatial_projection_complete=False,
             scalar_rounding_spatial_assignment_complete=False, full_C_energy_matrix_assembled=False,
             global_passivity_qualified=False, physical_RC_qualified=False, release_qualified=False))
        save(out/'status.json', dict(state='native_reference_delta_quantified', release_qualified=False))
        print(json.dumps({k: result[k] for k in ('union_upper_entries', 'outside_tolerance_entries', 'maximum_absolute_delta')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('reference', 'controls', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    run(args.reference, args.controls, args.output)
