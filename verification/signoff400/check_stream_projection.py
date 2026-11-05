"""Exercise actual-operator streaming, bounded flushes and external reduction."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal, localcontext
from fractions import Fraction
import json
from pathlib import Path
import shutil
import time
from common import ROOT, save, sha
from compiled_charge import execute
from resources import lease


def run(reference, output):
    reference, out = reference.resolve(), output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    deadline = time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    receipt = reference/'assessment.json'
    report = json.loads(receipt.read_text())
    if not report['compiled_geometry_provider_controls_pass']:
        raise ValueError('matching compiled geometry control required')
    cfg_path, old_matrices = reference/'config.json', reference/'matrices.jsonl'
    config = json.loads(cfg_path.read_text())
    cases = Path(config['cases'])
    compiler = Path(shutil.which('g++')).resolve()
    source = ROOT/'tools/sheet_charge'
    names = ('stream_project_charge.cpp', 'merge_sparse_runs.cpp', 'sparse_runs.hpp',
             'runtime_geometry_v2.hpp', 'main_registered_rational.cpp')
    paths = [receipt, cfg_path, old_matrices, cases, compiler, *[source/n for n in names],
             ROOT/'tools/charge_compiler/json.hpp', Path(__file__).resolve()]
    expected = dict(report['input_sha256'])
    expected.update({str(p): report['artifacts'][str(p)] for p in (cfg_path, old_matrices)})
    for p in map(Path, expected):
        if p not in paths:
            paths.append(p)
    with lease(8, 16, deadline):
        with ThreadPoolExecutor(max_workers=8) as pool:
            pins = dict(zip(map(str, paths), pool.map(sha, paths)))
        if any(pins[p] != digest for p, digest in expected.items()):
            raise ValueError('compiled geometry/reference source changed')
        binaries = {}
        for name in ('stream_project_charge', 'merge_sparse_runs'):
            binary = out/name
            command = [compiler, '-std=c++20', '-O3', '-fopenmp', '-Wall', '-Wextra', '-Wpedantic',
                       '-fno-fast-math', '-ffp-contract=off', source/(name+'.cpp'), '-lgmpxx', '-lgmp', '-o', binary]
            save(out/'status.json', dict(state='building_'+name, release_qualified=False))
            execute(command, out/(name+'.build.log'), deadline, 16)
            binaries[name] = binary
        actual_cases = json.loads(cases.read_text())
        mapping, lookup, operators = [0], {0: 0}, []
        for case in actual_cases:
            op = case['operator'][:]
            for i in (1, 2):
                field = op[i]
                if field not in lookup:
                    lookup[field] = len(mapping)
                    mapping.append(field)
                op[i] = lookup[field]
            operators.append(op)
        save(out/'field_map.json', mapping)
        with (out/'operators.jsonl').open('x') as stream:
            for op in operators:
                stream.write(json.dumps(op, separators=(',', ':'))+'\n')
        geometry = config['geometry']
        geometry['deadline_uptime'] = deadline
        cfg = out/'stream.config.json'
        save(cfg, dict(geometry=geometry, shards=[dict(operators=str(out/'operators.jsonl'),
             field_map=str(out/'field_map.json'))], threads=8, max_accumulator_entries=32,
             cache_limit_bytes_per_thread=16777216, max_records_per_shard=0,
             expected_operators=len(operators), output=str(out/'native'), deadline_uptime=deadline))
        save(out/'status.json', dict(state='streaming_actual_control_operators', release_qualified=False))
        execute([binaries['stream_project_charge'], cfg], out/'stream.log', deadline, 16)
        runs = sorted((out/'native').glob('shard_*_run_*.bin'))
        if not runs or len(runs) > 128:
            raise ValueError('bounded nonempty control sparse runs required')
        merge_cfg = out/'merge.config.json'
        save(merge_cfg, dict(inputs=list(map(str, runs)), output=str(out/'merged.bin'),
             json_output=str(out/'merged.jsonl'), deadline_uptime=deadline))
        execute([binaries['merge_sparse_runs'], merge_cfg], out/'merge.log', deadline, 16)
        # Independent Decimal accumulation of the already-oracle-checked matrices.
        wanted = {}
        with localcontext() as context:
            context.prec = 90
            for raw in old_matrices.read_text().splitlines():
                row = json.loads(raw)
                ids = row['global_nodes']
                if 'exact_matrix' in row:
                    entries = [(a, b, Decimal(n)/Decimal(d)) for a, b, n, d in row['exact_matrix']]
                else:
                    entries = [(a, b, Decimal.from_float(v)) for a, b, v in row['matrix']]
                for a, b, value in entries:
                    a, b = ids[a], ids[b]
                    if a <= b and value:
                        wanted[a, b] = wanted.get((a, b), Decimal(0))+value
            actual = {}
            for raw in (out/'merged.jsonl').read_text().splitlines():
                a, b, value, absolute, terms = json.loads(raw)
                if (a, b) in actual or a > b or terms <= 0 or Decimal(absolute) < 0:
                    raise ValueError('sparse merge record invariant')
                actual[a, b] = Decimal(value)
            norm = max([abs(value) for value in wanted.values()]+[Decimal(0)])
            error = max([abs(actual.get(k, 0)-wanted.get(k, 0)) for k in set(actual)|set(wanted)]+[Decimal(0)])
            normalized = error/norm if norm else error
            if normalized > Decimal('1e-14'):
                raise ValueError('streamed/reduced C matrix differs from independent sum')
        with ThreadPoolExecutor(max_workers=8) as pool:
            if list(pool.map(sha, paths)) != list(pins.values()):
                raise ValueError('stream control input changed')
        summary = json.loads((out/'stream.log').read_text())
        artifacts = [*binaries.values(), cfg, merge_cfg, out/'stream.log', out/'merge.log',
             out/'field_map.json', out/'operators.jsonl', out/'merged.bin', out/'merged.jsonl', *runs]
        save(out/'assessment.json', dict(input_sha256=pins, artifacts={str(p): sha(p) for p in artifacts},
             input_scope='actual_97_operator_control_fixture', operators=len(operators),
             sparse_runs=len(runs), reduced_upper_entries=len(actual),
             maximum_normalized_reduction_error=str(normalized), compiled_summary=summary,
             streamed_sparse_accumulation_controls_pass=True,
             full_native_operator_coverage=False, full_C_energy_matrix_assembled=False,
             physical_RC_qualified=False, release_qualified=False))
        save(out/'status.json', dict(state='stream_sparse_projection_controls_pass', release_qualified=False))
        print(json.dumps(dict(operators=len(operators), runs=len(runs), entries=len(actual), error=str(normalized))))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    run(args.reference, args.output)
