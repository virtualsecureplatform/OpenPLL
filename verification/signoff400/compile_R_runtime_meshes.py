"""Compile the full selected R mesh geometry with bounded parallel workers."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import shutil
import time
from common import ROOT, save, sha
from compiled_charge import execute
from resources import lease


def run(index, audit, output):
    index, audit, out = (p.resolve() for p in (index, audit, output))
    out.mkdir(parents=True, exist_ok=False)
    deadline = time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    receipt, proof = index/'assessment.json', audit/'assessment.json'
    report, checked = (json.loads(p.read_text()) for p in (receipt, proof))
    if checked['input_sha256'].get(str(receipt)) != sha(receipt) or not checked['all_field_slots_independently_checked']:
        raise ValueError('complete matching independent R index audit required')
    sources = [Path(report[k]) for k in ('catalog', 'axes', 'chains')]
    cpp = ROOT/'tools/sheet_charge/compile_R_meshes.cpp'
    compiler = Path(shutil.which('g++')).resolve()
    paths = [receipt, proof, *sources, cpp, compiler, ROOT/'tools/charge_compiler/json.hpp', Path(__file__).resolve()]
    with lease(8, 16, deadline):
        with ThreadPoolExecutor(max_workers=8) as pool:
            pins = dict(zip(map(str, paths), pool.map(sha, paths)))
        if any(pins[str(p)] != report['input_sha256'][str(p)] for p in sources):
            raise ValueError('R runtime sources differ from verified index')
        binary = out/'compile_R_meshes'
        command = [compiler, '-std=c++20', '-O3', '-fopenmp', '-Wall', '-Wextra', '-Wpedantic', cpp, '-o', binary]
        execute(command, out/'build.log', deadline, 16)
        cfg = out/'config.json'
        save(cfg, dict(catalog=str(sources[0]), axes=str(sources[1]), chains=str(sources[2]),
                       output=str(out/'native'), threads=8, expected_tiles=525638, deadline_uptime=deadline))
        save(out/'status.json', dict(state='compiling_all_selected_R_meshes', release_qualified=False))
        execute([binary, cfg], out/'native.log', deadline, 16)
        with ThreadPoolExecutor(max_workers=8) as pool:
            if list(pool.map(sha, paths)) != list(pins.values()):
                raise ValueError('R runtime input changed during compilation')
        result = json.loads((out/'native.log').read_text())
        artifacts = [binary, cfg, out/'native.log', *sorted((out/'native').glob('part_*.jsonl'))]
        save(out/'assessment.json', dict(**result, input_sha256=pins,
             artifacts={str(p): sha(p) for p in artifacts}, source_index=str(index),
             all_selected_R_tiles_compiled=True, independently_audited=False,
             full_C_energy_matrix_assembled=False, resistance_PVT_qualified=False))
        save(out/'status.json', dict(state='R_runtime_meshes_compiled_pending_independent_audit', release_qualified=False))
        print(json.dumps(result))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('index', 'audit', 'output'):
        parser.add_argument('--'+name, required=True, type=Path)
    args = parser.parse_args()
    run(args.index, args.audit, args.output)
