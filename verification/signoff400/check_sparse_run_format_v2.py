"""Adversarial sparse-stream format and compensated external-merge controls."""
import argparse
from decimal import Decimal
import json
from pathlib import Path
import shutil
import subprocess
import time
from common import ROOT, save, sha
from compiled_charge import execute
from resources import lease


def run(merger, output):
    merger, out = merger.resolve(), output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    deadline = time.clock_gettime(time.CLOCK_BOOTTIME)+3600
    cpp = ROOT/'tools/sheet_charge/sparse_run_controls.cpp'
    compiler = Path(shutil.which('g++')).resolve()
    paths = [merger, cpp, cpp.with_name('sparse_runs.hpp'), ROOT/'tools/charge_compiler/json.hpp',
             compiler, Path(__file__).resolve()]
    pins = {str(p): sha(p) for p in paths}
    with lease(2, 2, deadline):
        generator = out/'generate_sparse_controls'
        execute([compiler, '-std=c++20', '-O2', cpp, '-o', generator], out/'build.log', deadline, 1)
        execute([generator, out], out/'generator.log', deadline, 1)
        cfg = out/'positive.json'
        save(cfg, dict(inputs=[str(out/name) for name in ('a.bin', 'b.bin', 'c.bin')],
                       output=str(out/'positive.bin'), json_output=str(out/'positive.jsonl'), deadline_uptime=deadline))
        execute([merger, cfg], out/'positive.log', deadline, 1)
        rows = [json.loads(raw) for raw in (out/'positive.jsonl').read_text().splitlines()]
        values = {(a, b): (Decimal(value), terms) for a, b, value, absolute, terms in rows}
        if values != {(0, 0): (Decimal(1), 3), (0, 1): (Decimal(0), 2), (0, 2): (Decimal(7), 1)}:
            raise ValueError('external merge loses severe cancellation or term counts')
        original = bytearray((out/'a.bin').read_bytes())
        def change(offset, replacement):
            data = original[:]
            data[offset:offset+len(replacement)] = replacement
            return data
        malformed = {
            'short_header': original[:7], 'short_record': original[:-1],
            'trailing_bytes': original+b'x', 'wrong_magic': change(0, b'INVALID!'),
            'duplicate_key': change(56, original[16:24]),
            'descending_key': change(16, (2).to_bytes(8, 'little')),
            'nonfinite_value': change(24, bytes.fromhex('00000000000000c0ff7f')),
            'nonfinite_absolute': change(34, bytes.fromhex('00000000000000c0ff7f')),
            'reserved_byte': change(52, b'\x01'),
            'zero_terms': change(44, bytes(8)),
            'negative_absolute': change(43, bytes([original[43] | 128])),
            'short_count': change(8, (1).to_bytes(8, 'little')),
            'long_count': change(8, (3).to_bytes(8, 'little')),
            'absolute_below_signed': change(34, bytes(10)),
            'lower_triangle': change(56, (1 << 32).to_bytes(8, 'little')),
        }
        results = []
        for name, data in malformed.items():
            fixture, config, log = (out/(name+suffix) for suffix in ('.bin', '.json', '.log'))
            fixture.write_bytes(data)
            save(config, dict(inputs=[str(fixture)], output=str(out/(name+'.merged')), deadline_uptime=deadline))
            with log.open('x') as stream:
                result = subprocess.run([merger, config], stdout=stream, stderr=subprocess.STDOUT,
                                        timeout=30, check=False)
            results.append(dict(case=name, returncode=result.returncode, rejected=result.returncode == 2))
        save(out/'results.json', results)
        accepted = [r['case'] for r in results if not r['rejected']]
        save(out/'assessment.json', dict(input_sha256=pins,
             artifacts={str(p): sha(p) for p in (out/'results.json', out/'positive.jsonl', out/'positive.bin')},
             merger_binary=str(merger), severe_cancellation_and_term_counts_preserved=True, malformed_cases=len(results),
             rejected_malformed_cases=len(results)-len(accepted), unexpected_acceptances_or_crashes=accepted,
             all_sparse_format_controls_pass=not accepted, physical_RC_qualified=False, release_qualified=False))
        print(json.dumps(dict(cases=len(results), rejected=len(results)-len(accepted), failures=accepted)))
        if accepted:
            raise ValueError('sparse format controls failed: '+', '.join(accepted))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--merger', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    run(args.merger, args.output)
