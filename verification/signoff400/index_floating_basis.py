"""Build a bounded, parallel field lookup for audited floating-sheet instances."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import shutil
import time
from common import ROOT, save, sha
from compiled_charge import execute
from resources import lease


def run(instances, audit, output):
    instances, audit, out = (p.resolve() for p in (instances, audit, output))
    out.mkdir(parents=True, exist_ok=False)
    deadline = time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    receipt, proof = instances/'assessment.json', audit/'assessment.json'
    report, checked = (json.loads(p.read_text()) for p in (receipt, proof))
    if checked['input_sha256'].get(str(receipt)) != sha(receipt):
        raise ValueError('instance audit receipt mismatch')
    parts = [dict(native_type=t, path=str(instances/'native'/t/'instances.jsonl'))
             for t in ('li', 'm1', 'm2', 'm3', 'm4', 'm5', 'p')]
    cpp = ROOT/'tools/sheet_charge/index_floating_basis.cpp'
    compiler = Path(shutil.which('g++')).resolve()
    paths = [receipt, proof, cpp, ROOT/'tools/charge_compiler/json.hpp', compiler,
             Path(__file__).resolve(), *[Path(p['path']) for p in parts],
             *[instances/'atlas'/name for name in ('template_aliases.json', 'templates.jsonl')]]
    with lease(8, 8, deadline):
        save(out/'status.json', dict(state='hashing_audited_basis_sources', release_qualified=False))
        with ThreadPoolExecutor(max_workers=8) as pool:
            pins = dict(zip(map(str, paths), pool.map(sha, paths)))
        for p in parts:
            name = p['path']
            if pins[name] != report['artifacts'][name] or pins[name] != checked['input_sha256'][name]:
                raise ValueError('instance bytes differ from independent audit')
        for name in ('template_aliases.json', 'templates.jsonl'):
            p = str(instances/'atlas'/name)
            if pins[p] != report['artifacts'][p]:
                raise ValueError('atlas changed')
        binary = out/'index_floating_basis'
        execute([compiler, '-std=c++20', '-O3', '-fopenmp', '-Wall', '-Wextra', '-Wpedantic',
                 cpp, '-o', binary], out/'build.log', deadline, 8)
        cfg = out/'config.json'
        save(cfg, dict(partitions=parts, global_fields=2394896,
                       expected_instances=report['basis_instances'],
                       index=str(out/'fields.idx'), deadline_uptime=deadline))
        save(out/'status.json', dict(state='indexing_seven_material_partitions', release_qualified=False))
        execute([binary, cfg], out/'native.log', deadline, 8)
        with ThreadPoolExecutor(max_workers=8) as pool:
            if list(pool.map(sha, paths)) != list(pins.values()):
                raise ValueError('basis input changed during indexing')
        result = json.loads((out/'native.log').read_text())
        save(out/'assessment.json', dict(**result, input_sha256=pins,
             artifacts={str(p): sha(p) for p in (binary, cfg, out/'fields.idx', out/'native.log')},
             source_instances=str(instances), source_audit=str(audit), partitions=parts,
             index_format='FBSIDX01_le_u64_count_then_u64_offset_u32_length_u32_partition',
             physical_RC_qualified=False, full_C_energy_matrix_assembled=False))
        save(out/'status.json', dict(state='floating_basis_index_complete', release_qualified=False))
        print(json.dumps(result))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('instances', 'audit', 'output'):
        parser.add_argument('--'+name, required=True, type=Path)
    args = parser.parse_args()
    run(args.instances, args.audit, args.output)
