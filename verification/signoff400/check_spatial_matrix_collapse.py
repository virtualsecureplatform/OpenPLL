"""Verify P-transpose C P, upper symmetry factors, aliases and permutations."""
import argparse
import json
from pathlib import Path
import shutil
import struct
import time
from common import ROOT, save, sha
from compiled_charge import execute
from resources import lease


def run(merger_upgrade, output):
    merger_upgrade, out = merger_upgrade.resolve(), output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    deadline = time.clock_gettime(time.CLOCK_BOOTTIME)+3600
    proof = merger_upgrade/'assessment.json'
    checked = json.loads(proof.read_text())
    if not checked['actual_operator_merge_bytes_identical']:
        raise ValueError('validated sparse merger required')
    merger = Path(checked['merger_binary'])
    if sha(merger) != checked['input_sha256'][str(merger)]:
        raise ValueError('sparse merger changed')
    source = ROOT/'tools/sheet_charge'
    compiler = Path(shutil.which('g++')).resolve()
    paths = [proof, merger, compiler, Path(__file__).resolve(), ROOT/'tools/charge_compiler/json.hpp',
             *[source/p for p in ('spatial_collapse_fixture.cpp', 'collapse_spatial_matrix.cpp',
                'sparse_run_slice.hpp', 'sparse_runs_v2.hpp', 'conductor_map.hpp')]]
    pins = {str(p): sha(p) for p in paths}
    with lease(8, 8, deadline):
        binaries = {}
        for name in ('collapse_spatial_matrix', 'spatial_collapse_fixture'):
            binary = out/name
            execute([compiler, '-std=c++20', '-O3', '-fopenmp', '-Wall', '-Wextra', '-Wpedantic',
                     '-fno-fast-math', '-ffp-contract=off', source/(name+'.cpp'), '-o', binary],
                    out/(name+'.build.log'), deadline, 8)
            binaries[name] = binary
        execute([binaries['spatial_collapse_fixture'], out/'matrix.bin'], out/'fixture.log', deadline, 1)
        full = [[1, -1, -1, 1], [-1, 3, 1, -3], [-1, 1, 4, -4], [1, -3, -4, 6]]
        for label, mapping in (('normal', [0, 1, 1, 2]), ('permuted', [0, 2, 2, 1])):
            map_file = out/(label+'.bin')
            map_file.write_bytes(b'CNETDOF1'+struct.pack('<QQ4I', 4, 3, *mapping))
            expected = {}
            # Deliberately accumulate the FULL symmetric matrix, not upper entries.
            for a in range(4):
                for b in range(4):
                    i, j = mapping[a], mapping[b]
                    expected[i, j] = expected.get((i, j), 0)+full[a][b]
            expected = {k: v for k, v in expected.items() if k[0] <= k[1]}
            for threads in (1, 4, 8):
                root = out/f'{label}_{threads}'
                root.mkdir()
                cfg = root/'collapse.json'
                save(cfg, dict(matrix=str(out/'matrix.bin'), voltage_map=str(map_file),
                     threads=threads, max_accumulator_entries=16, output=str(root/'runs'), deadline_uptime=deadline))
                execute([binaries['collapse_spatial_matrix'], cfg], root/'collapse.log', deadline, 8)
                summary = json.loads((root/'collapse.log').read_text())
                if summary['source_upper_entries'] != 10 or summary['source_terms'] != 10 or summary['symmetry_doubled_entries'] != 1:
                    raise ValueError('spatial collapse source coverage or symmetry factor')
                merge = root/'merge.json'
                save(merge, dict(inputs=list(map(str, sorted((root/'runs').glob('*.bin')))),
                     output=str(root/'matrix.bin'), json_output=str(root/'matrix.jsonl'), deadline_uptime=deadline))
                execute([merger, merge], root/'merge.log', deadline, 1)
                actual = {(a, b): float(value) for a, b, value, absolute, terms in
                          map(json.loads, (root/'matrix.jsonl').read_text().splitlines())}
                if actual != expected:
                    raise ValueError('spatial collapse differs from independent full matrix transformation')
        if any(sha(Path(p)) != h for p, h in pins.items()):
            raise ValueError('spatial collapse control input changed')
        products = [*binaries.values(), out/'matrix.bin', *sorted(out.glob('*_*/matrix.bin')),
                    *sorted(out.glob('*_*/matrix.jsonl'))]
        save(out/'assessment.json', dict(input_sha256=pins, artifacts={str(p): sha(p) for p in products},
             spatial_conductor_collapse_controls_pass=True, thread_counts=[1, 4, 8],
             conductor_permutation_cases=2, full_symmetric_reference_used=True,
             same_conductor_offdiagonal_symmetry_factor_checked=True,
             upper_source_term_counts_preserved=True, physical_RC_qualified=False,
             full_C_energy_matrix_assembled=False, release_qualified=False))
        print(json.dumps(dict(thread_counts=[1, 4, 8], permutations=2, collapse_controls_pass=True)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--merger-upgrade', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.merger_upgrade, args.output)
