#!/usr/bin/env python3
"""Compiled reconciliation of raw native R snapshots against printed export.

Matching printed cards alone never qualifies physical domains or selects a
lifetime automatically. Build, hashing and comparison share a 12-hour budget.
"""
import argparse
from datetime import datetime, timezone
import json
import subprocess
from pathlib import Path
import time

from common import ROOT, save, sha
from compiled_charge import execute
from parallel_hash import sha_prefetch
from resources import lease

SOURCE = ROOT / 'tools/native_r_export_audit/main.cpp'
HEADER = ROOT / 'tools/charge_compiler/json.hpp'


def run(native, export, output):
    native, export, out = (Path(p).resolve() for p in (native, export, output))
    out.mkdir(parents=True, exist_ok=False)
    started = time.clock_gettime(time.CLOCK_BOOTTIME)
    deadline = started + 43200
    save(out / 'owner.json', dict(started_utc=datetime.now(timezone.utc).isoformat(),
         wall_limit_s=43200, automatic_identical_retry=False, cpu_slots=8, memory_limit_GiB=8))
    def status(state, **extra):
        save(out / 'status.json', dict(state=state,
             elapsed_s=time.clock_gettime(time.CLOCK_BOOTTIME)-started,
             release_qualified=False, **extra))
    def snapshot(paths):
        return {str(p):(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
                for p in paths for s in (p.stat(),)}
    try:
        status('waiting_for_resources')
        with lease(8, 8, deadline):
            paths=[native,export,SOURCE,HEADER,Path(__file__).resolve()]
            paths += [Path(__file__).with_name(n) for n in
                      ('common.py','compiled_charge.py','parallel_hash.py','resources.py')]
            initial=snapshot(paths)
            status('hashing_native_and_export_inputs')
            pins={str(p):sha_prefetch(p,deadline=deadline) for p in paths}
            save(out / 'input_manifest.json', dict(input_sha256=pins))
            binary=out / 'native_r_export_audit'
            command=['g++','-std=c++20','-O3','-Wall','-Wextra','-Wpedantic',
                     '-fno-fast-math','-ffp-contract=off',str(SOURCE),'-o',str(binary)]
            status('building_compiled_comparator')
            execute(command,out / 'build.log',deadline,8)
            config=out / 'compare.config.json'
            save(config,dict(native=str(native),export=str(export),output=str(out / 'native'),
                             deadline_uptime=deadline))
            status('comparing_printed_node_and_resistor_cards')
            execute([binary,config],out / 'compare.log',deadline,8)
            if initial!=snapshot(paths):
                raise ValueError('audit input changed while comparing native groups')
            summary=json.loads((out / 'native/summary.json').read_text())
            summary['input_sha256']=pins
            summary['artifacts']={str(p):sha(p) for p in
                    (binary,config,out / 'native/groups.jsonl',out / 'native/summary.json')}
            summary['build_command']=command
            summary['compiler_version']=subprocess.check_output(['g++','--version'],text=True)
            summary['elapsed_s']=time.clock_gettime(time.CLOCK_BOOTTIME)-started
            summary['physical_domain_complete']=False
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:
                raise TimeoutError('whole-check deadline exhausted during assessment')
            save(out / 'assessment.json',summary)
            status('printed_card_comparison_complete_pending_domain_reconciliation',
                   native_groups=summary['native_groups'], matching_printed_groups=summary['matching_printed_groups'])
            return summary
    except BaseException as error:
        status('failed',reason=repr(error))
        raise


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--native',required=True,type=Path)
    p.add_argument('--export',dest='export_path',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path)
    a=p.parse_args()
    r=run(a.native,a.export_path,a.output)
    print(json.dumps({k:r[k] for k in ('native_groups','matching_printed_groups',
          'labels_with_no_matching_group','labels_with_one_matching_group',
          'labels_with_multiple_matching_groups','elapsed_s')}))


if __name__=='__main__':
    main()
