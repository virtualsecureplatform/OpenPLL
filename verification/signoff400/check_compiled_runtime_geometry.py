"""Build the compiled shared geometry provider and compare real mixed matrices."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import shutil
import time
from common import ROOT, save, sha
from compiled_charge import execute
from compiled_sheet_charge_rational import decode
from resources import lease


def run(runtime, audit, R_index, floating_index, reference, output):
    runtime, audit, R_index, floating_index, reference, out = (p.resolve() for p in
        (runtime, audit, R_index, floating_index, reference, output))
    out.mkdir(parents=True, exist_ok=False)
    deadline = time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    rr, ar, ir, fr, pr = [p/'assessment.json' for p in (runtime, audit, R_index, floating_index, reference)]
    r, a, ri, f, p = [json.loads(path.read_text()) for path in (rr, ar, ir, fr, pr)]
    if not a['all_selected_R_meshes_independently_reconstructed'] or a['input_sha256'].get(str(rr)) != sha(rr):
        raise ValueError('full matching R mesh audit required')
    if r['input_sha256'].get(str(ir)) != sha(ir) or p['input_sha256'].get(str(ir)) != sha(ir):
        raise ValueError('compiled/reference R index mismatch')
    if p['input_sha256'].get(str(fr)) != sha(fr) or not p['real_native_signed_operator_controls_passed']:
        raise ValueError('compiled/reference floating index mismatch')
    parts = sorted(runtime.glob('native/part_*.jsonl'))
    root = Path(f['source_instances'])
    floating = [Path(row['path']) for row in f['partitions']]
    cases, matrices = reference/'projection/cases.json', reference/'projection/matrices.jsonl'
    expected = {str(path): r['artifacts'][str(path)] for path in parts}
    expected.update({str(path): f['input_sha256'][str(path)] for path in floating})
    for path in (R_index/'fields.idx', Path(ri['bundles'])):
        expected[str(path)] = ri['artifacts'].get(str(path), ri['input_sha256'].get(str(path)))
    for path in (root/'atlas/templates.jsonl', root/'atlas/template_aliases.json'):
        expected[str(path)] = f['input_sha256'][str(path)]
    expected.update({str(path): p['artifacts'][str(path)] for path in (cases, matrices)})
    compiler = Path(shutil.which('g++')).resolve()
    cpp = ROOT/'tools/sheet_charge/project_runtime_controls.cpp'
    source = [cpp, cpp.with_name('runtime_geometry.hpp'), cpp.with_name('main_registered_rational.cpp'),
              ROOT/'tools/charge_compiler/json.hpp']
    paths = [rr, ar, ir, fr, pr, compiler, *source, Path(__file__).resolve(), *map(Path, expected)]
    with lease(8, 16, deadline):
        with ThreadPoolExecutor(max_workers=8) as pool:
            pins = dict(zip(map(str, paths), pool.map(sha, paths)))
        if any(pins[path] != digest for path, digest in expected.items()):
            raise ValueError('compiled runtime source/reference bytes changed')
        binary = out/'project_runtime_controls'
        command = [compiler, '-std=c++20', '-O3', '-fopenmp', '-Wall', '-Wextra', '-Wpedantic',
                   '-fno-fast-math', '-ffp-contract=off', cpp, '-lgmpxx', '-lgmp', '-o', binary]
        save(out/'status.json', dict(state='building_compiled_runtime_geometry', release_qualified=False))
        execute(command, out/'build.log', deadline, 16)
        geometry = dict(global_fields=ri['global_fields'], R_parts=list(map(str, parts)),
             expected_R_tiles=r['tiles'], R_index=str(R_index/'fields.idx'),
             expected_R_fields=ri['R_fields'], R_bundles=ri['bundles'],
             template_aliases=str(root/'atlas/template_aliases.json'), templates=str(root/'atlas/templates.jsonl'),
             floating_parts=list(map(str, floating)), expected_floating_fields=f['indexed_instances'],
             expected_floating_nodes=7500317, deadline_uptime=deadline)
        cfg = out/'config.json'
        save(cfg, dict(geometry=geometry, cases=str(cases), output=str(out/'matrices.jsonl'),
                       threads=8, deadline_uptime=deadline))
        save(out/'status.json', dict(state='resolving_and_projecting_without_Python_meshes', release_qualified=False))
        execute([binary, cfg], out/'native.log', deadline, 16)
        rows = [json.loads(raw) for raw in (out/'matrices.jsonl').read_text().splitlines()]
        previous = [json.loads(raw) for raw in matrices.read_text().splitlines()]
        operators = json.loads(cases.read_text())
        if len(rows) != len(previous) or len(rows) != len(operators):
            raise ValueError('compiled runtime projection coverage')
        maximum = 0.0
        for case, row, old in zip(operators, rows, previous):
            if case['id'] != row['id'] or row['id'] != old['id']:
                raise ValueError('compiled runtime case identity')
            exact = case['operator'][0] != 'F'
            actual, wanted = decode(row, exact), decode(old, exact)
            if exact:
                if actual != wanted:
                    raise ValueError('compiled resolved A/L projection differs')
            else:
                norm = max([abs(v) for v in wanted.values()]+[0.0])
                delta = max([abs(actual.get(k, 0)-wanted.get(k, 0)) for k in set(actual)|set(wanted)]+[0.0])
                error = delta/norm if norm else delta
                maximum = max(maximum, error)
                if error > 1e-14:
                    raise ValueError('compiled resolved fringe projection differs')
        with ThreadPoolExecutor(max_workers=8) as pool:
            if list(pool.map(sha, paths)) != list(pins.values()):
                raise ValueError('compiled runtime input changed')
        summary = json.loads((out/'native.log').read_text())
        save(out/'assessment.json', dict(input_sha256=pins,
             artifacts={str(path): sha(path) for path in (binary, cfg, out/'native.log', out/'matrices.jsonl')},
             compiled_summary=summary, actual_mixed_cases_checked=len(rows),
             maximum_normalized_fringe_delta=maximum, compiled_geometry_provider_controls_pass=True,
             full_C_energy_matrix_assembled=False, physical_RC_qualified=False,
             resistance_PVT_qualified=False, release_qualified=False))
        save(out/'status.json', dict(state='compiled_runtime_geometry_controls_pass', release_qualified=False))
        print(json.dumps(dict(cases=len(rows), maximum_delta=maximum, **summary)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('runtime', 'audit', 'R-index', 'floating-index', 'reference', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    run(args.runtime, args.audit, args.R_index, args.floating_index, args.reference, args.output)
