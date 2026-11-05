#!/usr/bin/env python3
"""Audit all retained R snapshot wire geometry with bounded compiled code."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import time
from common import ROOT, save, sha, verify
from compile_charge import pins
from compiled_charge_v2 import execute
from resources import lease

SOURCE = ROOT / 'tools/native_r_geometry_audit/main.cpp'
HEADER = ROOT / 'tools/charge_compiler/json.hpp'


def run(index, native, segments, output):
    index, native, segments, out = (Path(p).resolve() for p in (index, native, segments, output))
    out.mkdir(parents=True, exist_ok=False)
    started = time.clock_gettime(time.CLOCK_BOOTTIME)
    deadline = started + 43200
    save(out / 'owner.json', dict(started_utc=datetime.now(timezone.utc).isoformat(),
         wall_limit_s=43200, automatic_identical_retry=False, cpu_slots=8, memory_limit_GiB=8))

    def status(state, **kw):
        save(out / 'status.json', dict(state=state, elapsed_s=time.clock_gettime(time.CLOCK_BOOTTIME)-started,
             release_qualified=False, **kw))

    def snapshot(paths):
        return {str(p): (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
                for p in paths for s in (p.stat(),)}

    try:
        with lease(8, 8, deadline):
            status('verifying_native_index')
            report = json.loads((index / 'assessment.json').read_text())
            if not report.get('all_native_groups_and_snapshot_records_preserved'):
                raise ValueError('index must retain all native snapshots')
            paths = [native, segments, index / 'nodes.json', index / 'tile_domains.jsonl',
                     index / 'assessment.json', SOURCE, HEADER, Path(__file__).resolve()]
            paths += [Path(__file__).with_name(n) for n in
                      ('common.py', 'compile_charge.py', 'compiled_charge.py', 'compiled_charge_v2.py',
                       'parallel_hash.py', 'resources.py')]
            control_paths=[Path(p) for p in report['input_sha256'] if Path(p).name=='assessment.json']
            if len(control_paths)!=1:raise ValueError('native domain receipt missing or ambiguous')
            control=control_paths[0];verify({str(control):report['input_sha256'][str(control)]})
            domain=json.loads(control.read_text())
            if not domain.get('native_rc_export_completed'):raise ValueError('native RC export incomplete')
            paths.append(control)
            initial = snapshot(paths)
            input_pins = pins(paths, deadline, lambda **kw: status('hashing_native_geometry_inputs', **kw))
            if report['input_sha256'].get(str(native)) != input_pins[str(native)]:
                raise ValueError('native index provenance identity mismatch')
            for name in ('nodes.json', 'tile_domains.jsonl'):
                path = index / name
                if report['artifacts'].get(str(path)) != input_pins[str(path)]:
                    raise ValueError('indexed geometry artifact identity mismatch')
            for path in (native,segments):
                if domain['artifacts'].get(str(path))!=input_pins[str(path)]:
                    raise ValueError('native domain stream identity mismatch')
            save(out / 'input_manifest.json', dict(input_sha256=input_pins))
            binary = out / 'native_r_geometry_audit'
            command = ['g++', '-std=c++20', '-O3', '-Wall', '-Wextra', '-Wpedantic',
                       '-fno-fast-math', '-ffp-contract=off', str(SOURCE), '-o', str(binary)]
            status('building_compiled_auditor')
            execute(command, out / 'build.log', deadline, 8)
            config = out / 'audit.config.json'
            save(config, dict(native=str(native), segments=str(segments), nodes=str(index / 'nodes.json'),
                 tiles=str(index / 'tile_domains.jsonl'), output=str(out / 'native'), deadline_uptime=deadline))
            status('matching_creation_geometry_and_resolved_breakpoints')
            execute([binary, config], out / 'audit.log', deadline, 8)
            if initial != snapshot(paths):
                raise ValueError('native geometry input changed during audit')
            result = json.loads((out / 'native/summary.json').read_text())
            if result['native_nodes'] != report['private_nodes'] or result['native_groups'] != report['native_groups']:
                raise ValueError('native index node/group coverage mismatch')
            if result['native_tiles'] != report['domain_counts']['domains']:
                raise ValueError('native index tile coverage mismatch')
            result.update(input_sha256=input_pins,
                artifacts={str(p): sha(p) for p in (binary, config, out / 'native/summary.json',
                           out / 'native/groups.jsonl', out / 'native/failures.jsonl')},
                build_command=command, compiler_version=subprocess.check_output(['g++', '--version'], text=True),
                elapsed_s=time.clock_gettime(time.CLOCK_BOOTTIME)-started)
            if time.clock_gettime(time.CLOCK_BOOTTIME) >= deadline:
                raise TimeoutError('whole-check deadline exhausted during assessment')
            save(out / 'assessment.json', result)
            status('wire_geometry_match' if result['all_wire_creation_geometry_matched'] else 'wire_geometry_nonpass',
                   wire_branches=result['wire_branches'], failures=result['wire_geometry_failures'])
            return result
    except BaseException as error:
        status('failed', reason=repr(error)); raise


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('index', 'native', 'segments', 'output'):
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()
    result = run(a.index, a.native, a.segments, a.output)
    print(json.dumps({k: result[k] for k in ('wire_branches', 'wire_geometry_failures', 'elapsed_s')}))
