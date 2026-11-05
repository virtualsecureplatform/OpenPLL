#!/usr/bin/env python3
"""Bounded compiled sufficient equality proof; retains the original native deadline.

A nonpass is inconclusive and cannot replace the existing Decimal comparison.
This tool neither stops that controller nor changes its artifacts or gates.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import time
from common import ROOT, save, sha
from compiled_charge import execute
from resources import lease


def run(native_charge, output):
    native, out = Path(native_charge).resolve(), Path(output).resolve()
    out.mkdir(parents=True, exist_ok=False)
    start = time.clock_gettime(time.CLOCK_BOOTTIME)
    owner = json.loads((native/'owner.json').read_text())
    elapsed = (datetime.now(timezone.utc)-datetime.fromisoformat(owner['budget_started_utc'])).total_seconds()
    deadline = start+owner['wall_limit_s']-max(0, elapsed)
    def status(state, **extra):
        save(out/'status.json', dict(state=state, release_qualified=False,
             elapsed_s=time.clock_gettime(time.CLOCK_BOOTTIME)-start, **extra))
    save(out/'owner.json', dict(original_owner=str(native/'owner.json'),
         original_budget_started_utc=owner['budget_started_utc'], deadline_uptime=deadline,
         total_budget_restarted=False, automatic_identical_retry=False, cpu_slots=16,
         memory_limit_GiB=12, running_reference_controller_unchanged=True))
    try:
        if deadline <= start:
            raise TimeoutError('original native comparison deadline exhausted')
        with lease(16, 12, deadline):
            status('pinning_complete_native_card_inputs')
            trace = native/'trace'
            if 'FILLED_OWNER_C_NATIVE_COMPLETE' not in (trace/'extract.log').read_text():
                raise ValueError('native trace completion marker required')
            manifest = native/'input_manifest.json'
            upstream = json.loads(manifest.read_text())['input_sha256']
            references = [Path(p) for p in upstream if p.endswith('/domain/trace/pre_resistance.spice')]
            if len(references) != 1:
                raise ValueError('unique pinned native reference SPICE required')
            left = references[0]
            right = trace/'pre_resistance.spice'
            left_ext = left.with_name('Prototype400_FilledCapacitanceView.ext')
            right_ext = right.with_name(left_ext.name)
            compiler = Path(shutil.which('g++')).resolve()
            cpp = ROOT/'tools/native_rc_coverage/compare_native_cards.cpp'
            paths = [left, right, left_ext, right_ext, manifest, native/'owner.json', trace/'extract.log',
                     compiler, cpp, ROOT/'tools/charge_compiler/json.hpp', Path(__file__).resolve(),
                     *[Path(__file__).with_name(n) for n in ('common.py', 'compiled_charge.py', 'resources.py')]]
            pins = {str(p): sha(p) for p in paths}
            if any(pins[str(p)] != upstream.get(str(p)) for p in (left, left_ext)):
                raise ValueError('reference card file differs from original trace pins')
            save(out/'input_manifest.json', dict(input_sha256=pins))
            binary = out/'compare_native_cards'
            command = [compiler, '-std=c++20', '-O3', '-fopenmp', '-fno-fast-math',
                       '-ffp-contract=off', '-Wall', '-Wextra', '-Wpedantic', cpp, '-o', binary]
            execute(command, out/'build.log', deadline, 12)
            save(out/'build.json', dict(command=list(map(str, command)),
                 compiler_version=subprocess.check_output([compiler, '--version'], text=True)))
            cfg = out/'config.json'
            save(cfg, dict(left_spice=str(left), right_spice=str(right), left_ext=str(left_ext),
                 right_ext=str(right_ext), deadline_uptime=deadline, threads=16))
            status('compiled_parallel_card_comparison_running')
            execute([binary, cfg], out/'native.log', deadline, 12)
            result = json.loads((out/'native.log').read_text())
            for p, h in pins.items():
                if sha(p) != h:
                    raise ValueError('card comparison input changed: '+p)
            result.update(input_sha256=pins, artifacts={str(p): sha(p) for p in
                 (binary, out/'build.log', out/'build.json', cfg, out/'native.log')},
                 original_deadline_preserved=True, reference_controller_replaced=False,
                 original_floating_nodes_unchanged=True, physical_RC_qualified=False,
                 runtime_model_eligible=False, elapsed_s=time.clock_gettime(time.CLOCK_BOOTTIME)-start)
            save(out/'assessment.json', result)
            status('sufficient_exact_card_equality_proven_physical_RC_pending')
            return result
    except BaseException as exc:
        status('inconclusive_or_failed', reason=repr(exc))
        raise


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--native-charge', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    print(json.dumps(run(a.native_charge, a.output)))
