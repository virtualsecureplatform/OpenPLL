"""Control capacitor-to-matrix signs, conductor aliases and clamp bookkeeping."""
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
        raise ValueError('controlled merger changed')
    source = ROOT/'tools/sheet_charge/collapse_native_cap_ledger.cpp'
    compiler = Path(shutil.which('g++')).resolve()
    paths = [proof, merger, source, source.with_name('conductor_map.hpp'), source.with_name('sparse_runs_v2.hpp'),
             ROOT/'tools/charge_compiler/json.hpp', compiler, Path(__file__).resolve()]
    pins = {str(p): sha(p) for p in paths}
    with lease(8, 8, deadline):
        binary = out/'collapse_native_cap_ledger'
        execute([compiler, '-std=c++20', '-O3', '-fopenmp', '-Wall', '-Wextra', '-Wpedantic',
                 '-fno-fast-math', '-ffp-contract=off', source, '-o', binary], out/'build.log', deadline, 8)
        # Fields 1 and 2 share an ideal conductor. Column 2 is native delta;
        # column 3 is the retained physical operator integral.
        ledger = [[0, 1, 2, 2, 0], [0, 2, 3, 0, 3], [0, 3, -1, -1, 0],
                  [1, 2, 5, 5, 0], [1, 3, 7, 7, 0]]
        save(out/'ledger.json', ledger)
        (out/'field_nets.bin').write_bytes(b'CNETFLD1'+struct.pack('<QQ4I', 4, 3, 0, 1, 1, 2))
        expected = {
            'physical': {(0, 0): 1, (0, 1): -2, (0, 2): 1, (1, 1): 9, (1, 2): -7, (2, 2): 6},
            'native': {(0, 0): 4, (0, 1): -5, (0, 2): 1, (1, 1): 12, (1, 2): -7, (2, 2): 6},
        }
        for threads in (1, 4, 8):
            root = out/f'threads_{threads}'
            root.mkdir()
            cfg = root/'config.json'
            save(cfg, dict(ledger=str(out/'ledger.json'), field_map=str(out/'field_nets.bin'),
                 output=str(root/'runs'), threads=threads, max_accumulator_entries=16,
                 expected_rows=len(ledger), deadline_uptime=deadline))
            execute([binary, cfg], root/'native.log', deadline, 8)
            summary = json.loads((root/'native.log').read_text())
            if summary['ledger_rows'] != 5 or summary['same_conductor_scalar_edges_ignored'] != 1:
                raise ValueError('parallel scalar-ledger row/alias coverage')
            for kind in ('physical', 'native'):
                runs = sorted((root/'runs').glob(kind+'_part_*.bin'))
                config = root/(kind+'.json')
                save(config, dict(inputs=list(map(str, runs)), output=str(root/(kind+'.bin')),
                     json_output=str(root/(kind+'.jsonl')), deadline_uptime=deadline))
                execute([merger, config], root/(kind+'.log'), deadline, 1)
                actual = {(a, b): float(value) for a, b, value, absolute, terms in
                          map(json.loads, (root/(kind+'.jsonl')).read_text().splitlines())}
                if actual != expected[kind]:
                    raise ValueError('native scalar ledger is expanded or aliased incorrectly')
        if any(sha(Path(p)) != h for p, h in pins.items()):
            raise ValueError('native ledger collapse control input changed')
        artifacts = [binary, *sorted(out.glob('threads_*/*.jsonl')), out/'ledger.json', out/'field_nets.bin']
        save(out/'assessment.json', dict(input_sha256=pins, artifacts={str(p): sha(p) for p in artifacts},
             capacitor_scalar_expansion_controls_pass=True, thread_counts=[1, 4, 8],
             conductor_alias_cancellation_checked=True, native_and_physical_columns_distinguished=True,
             signed_scalar_capacitors_checked=True, full_C_energy_matrix_assembled=False,
             physical_RC_qualified=False, release_qualified=False))
        print(json.dumps(dict(thread_counts=[1, 4, 8], expansion_and_alias_controls_pass=True)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--merger-upgrade', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.merger_upgrade, args.output)
