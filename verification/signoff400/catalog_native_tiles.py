#!/usr/bin/env python3
"""Compiled complete native tile/axis catalog with bounded local staging."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from common import ROOT, save, sha
from compiled_charge import execute
from resources import lease
from nominal_sheet_resistance_v3 import parse


def run(index, axes, audit, output):
    index, axes, audit, out = (Path(p).resolve() for p in (index, axes, audit, output))
    out.mkdir(parents=True, exist_ok=False)
    start = time.clock_gettime(time.CLOCK_BOOTTIME)
    deadline, scratch = start+43200, None
    def status(state, **extra):
        save(out/'status.json', dict(state=state, release_qualified=False,
             elapsed_s=time.clock_gettime(time.CLOCK_BOOTTIME)-start, **extra))
    save(out/'owner.json', dict(wall_limit_s=43200, cpu_slots=2, memory_limit_GiB=8,
                               automatic_identical_retry=False, local_scratch=True))
    try:
        with lease(2, 8, deadline):
            status('validating_axis_audit_and_native_tile_lineage')
            ir, ar, vr = (p/'assessment.json' for p in (index, axes, audit))
            i, a, v = (json.loads(p.read_text()) for p in (ir, ar, vr))
            if not v['all_registry_rows_independently_checked'] or v['input_sha256'].get(str(ar)) != sha(ar):
                raise ValueError('complete independent axis audit required')
            domains = [Path(p) for p in i['input_sha256'] if p.endswith('/domain/assessment.json')]
            if len(domains) != 1 or a['input_sha256'].get(str(domains[0])) != i['input_sha256'][str(domains[0])]:
                raise ValueError('tile and axis native domain mismatch')
            domain = domains[0]
            if sha(domain) != i['input_sha256'][str(domain)]:
                raise ValueError('native domain receipt changed')
            d = json.loads(domain.read_text())
            tech = ROOT/'build/timing450/pdk/sky130A/libs.tech/magic/sky130A.tech'
            if d['input_sha256'].get(str(tech)) != sha(tech):
                raise ValueError('native nominal technology mismatch')
            sources = [index/'tile_domains.jsonl', axes/'native/axis_registry.jsonl']
            source_hashes = [i['artifacts'][str(sources[0])], a['artifacts'][str(sources[1])]]
            if v['input_sha256'].get(str(sources[1])) != source_hashes[1]:
                raise ValueError('audited registry bytes mismatch')
            compiler = Path(shutil.which('g++')).resolve()
            cpp = ROOT/'tools/native_rc_coverage/catalog_native_tiles.cpp'
            paths = [ir, ar, vr, domain, tech, compiler, cpp, ROOT/'tools/charge_compiler/json.hpp',
                     Path(__file__).resolve(), *[Path(__file__).with_name(n) for n in
                     ('common.py', 'compiled_charge.py', 'resources.py', 'nominal_sheet_resistance.py',
                      'nominal_sheet_resistance_v2.py', 'nominal_sheet_resistance_v3.py')]]
            pins = {str(p): sha(p) for p in paths}
            pins.update({str(p): h for p, h in zip(sources, source_hashes)})
            size = sum(p.stat().st_size for p in sources)
            if shutil.disk_usage('/tmp').free < size*4+32*1024**3:
                raise ValueError('insufficient bounded local scratch reserve')
            scratch = Path(tempfile.mkdtemp(prefix='openpll-native-tile-catalog-', dir='/tmp'))
            save(out/'staging.json', dict(directory=str(scratch), cleanup_after_verified_publish=True))
            status('staging_and_rehashing_complete_tile_and_axis_streams')
            for source, name, h in zip(sources, ('tiles.jsonl', 'axes.jsonl'), source_hashes):
                shutil.copyfile(source, scratch/name)
                if sha(scratch/name) != h:
                    raise ValueError('complete producer stream differs from staged bytes')
            binary = scratch/'catalog_native_tiles'
            command = [compiler, '-std=c++20', '-O3', '-Wall', '-Wextra', '-Wpedantic', cpp, '-o', binary]
            execute(command, scratch/'build.log', deadline, 8)
            cfg = scratch/'config.json'
            save(cfg, dict(tiles=str(scratch/'tiles.jsonl'), axes=str(scratch/'axes.jsonl'),
                 nominal_sheet_values={k: str(value) for k, value in parse(tech.read_text()).items()},
                 output=str(scratch/'native'), deadline_uptime=deadline))
            status('compiled_full_native_tile_join_running')
            execute([binary, cfg], scratch/'native.log', deadline, 8)
            result = json.loads((scratch/'native/summary.json').read_text())
            if result['native_tiles'] != i['domain_counts']['domains'] or result['axis_records_matched_once'] != a['source_chains']:
                raise ValueError('full native tile/axis coverage mismatch')
            status('publishing_byte_verified_native_tile_catalog')
            artifacts = {}
            for name in ('catalog_native_tiles', 'build.log', 'config.json', 'native.log',
                         'native/summary.json', 'native/tile_catalog.jsonl'):
                source, target = scratch/name, out/name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
                if sha(target) != sha(source):
                    raise ValueError('published catalog differs from local result')
                artifacts[str(target)] = sha(target)
            for p, h in pins.items():
                if sha(p) != h:
                    raise ValueError('catalog input changed: '+p)
            result.update(input_sha256=pins, artifacts=artifacts,
                          local_staged_bytes_equal_published=True, finite_element_matrices_materialized=False,
                          full_native_inputs_rehashed=False, elapsed_s=time.clock_gettime(time.CLOCK_BOOTTIME)-start)
            save(out/'assessment.json', result)
            shutil.rmtree(scratch)
            status('native_tile_catalog_complete_physical_RC_qualification_pending')
            return result
    except BaseException as exc:
        status('failed', reason=repr(exc), retained_scratch=str(scratch) if scratch else None)
        raise


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('index', 'axes', 'audit', 'output'):
        p.add_argument('--'+name, required=True, type=Path)
    a = p.parse_args()
    print(json.dumps(run(a.index, a.axes, a.audit, a.output)))
