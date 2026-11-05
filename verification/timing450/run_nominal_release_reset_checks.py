#!/usr/bin/env python3
"""Run a bounded nominal-only reset batch, retaining prior independent passes.

This is interface evidence, not whole-PLL or release qualification. Frozen
campaigns and their helpers are never modified or restarted.
"""
import argparse
import concurrent.futures
from datetime import datetime, timezone
from itertools import product
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import threading
import time
from characterize_bbpd import sha, verify
from loaded_reset_withdrawal_profile import validate_withdrawal


def save(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    temporary.replace(path)


def permitted(case, requirements):
    return (case['supply_v'] == 1.8 and requirements['voltages'] == [1.8]
            and case['corner'] in requirements['corners']
            and case['temperature_c'] in requirements['temperatures_c']
            and case['mode_mhz'] in requirements['modes_mhz'])


def priority(case):
    # Cover all three previously untested nominal modes before filling a grid.
    pilot = case['mode_mhz'] in (250, 300, 400) and (
        (case['corner'], case['temperature_c'], case['edge_ps'])
        in [('ss', 125, 20), ('fs', 125, 200)])
    return (not pilot, case['corner'] != 'ss', case['edge_ps'],
            case['phase_ps'], case['mode_mhz'], case['temperature_c'], case['corner'])


def command(argv, log, deadline):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        return 124
    with log.open('w') as stream:
        child = subprocess.Popen(argv, stdout=stream, stderr=subprocess.STDOUT,
                                 start_new_session=True)
        try:
            return child.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGTERM)
            try:
                child.wait(timeout=30)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()
            return 124


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--validate-only', action='store_true')
    parser.add_argument('--max-new-checks', type=int, default=12)
    parser.add_argument('--workers', type=int, default=4)
    args = parser.parse_args()
    assert 1 <= args.max_new_checks <= 12 and 1 <= args.workers <= 4
    output = args.output.resolve()
    assert not output.exists()
    root = Path.cwd()
    here = Path(__file__).resolve().parent
    c = root / 'build/timing450/interface_characterization'
    requirement_path = root / 'verification/release_requirements.json'
    requirements = json.loads(requirement_path.read_text())
    assert requirements['voltages'] == [1.8]
    pins = {str(requirement_path): sha(requirement_path), str(Path(__file__).resolve()): sha(Path(__file__))}

    def merge(mapping):
        for path, digest in mapping.items():
            assert path not in pins or pins[path] == digest, path
            pins[path] = digest

    cases = {}
    recipes = ['receiver_loaded_reset_pvt_grid_prepared_001',
               'receiver_loaded_reset_remaining_modes_prepared_001']
    for name in recipes:
        path = c / name / 'preparation.json'
        recipe = json.loads(path.read_text())
        merge(recipe['source_sha256'])
        pins[str(path)] = sha(path)
        for original in recipe['prepared_cases']:
            case = dict(original)
            case.setdefault('mode_mhz', 450)
            if not permitted(case, requirements):
                continue
            case.setdefault('simulation_time_ns', 350)
            case.setdefault('withdrawal_start_ns', 187.05)
            source = Path(case['directory']) / 'loaded.cir'
            assert sha(source) == case['deck_sha256']
            validate_withdrawal(source.read_text(), case['mode_mhz'], case['withdrawal_start_ns'])
            name = f"{case['mode_mhz']}MHz_" + Path(case['directory']).name
            assert name not in cases
            cases[name] = case
    expected = set(product(requirements['modes_mhz'], requirements['corners'],
                           [1.8], requirements['temperatures_c'], [-250, 250], [20, 200]))
    assert len(cases) == 300
    assert {tuple(case[k] for k in ('mode_mhz','corner','supply_v','temperature_c','phase_ps','edge_ps'))
            for case in cases.values()} == expected
    records = {}
    for name in ['receiver_loaded_reset_campaign_independent_terminals_001',
                 'receiver_loaded_reset_remaining_modes_native_001']:
        status_path = c / name / 'status.json'
        status = json.loads(status_path.read_text())
        # Discovery status stays mutable; only completed immutable receipts pin evidence.
        for key, record in status['cases'].items():
            if key not in cases or not record.get('terminal') or not record.get('independent_verification_pass'):
                continue
            receipt = Path(record.get('independent_receipt', str(c / name / (key + '_independent.json'))))
            assessed = json.loads(receipt.read_text())
            assert assessed['pass'] and assessed['pvt']['supply_v'] == 1.8
            assert assessed['mode_mhz'] == cases[key]['mode_mhz']
            assert sha(receipt) == record['independent_assessment_sha256']
            native = Path(record.get('native_directory', record.get('directory', '')))
            assert (native / 'loaded.cir').read_bytes() == (Path(cases[key]['directory']) / 'loaded.cir').read_bytes()
            merge(assessed['sha256'])
            pins[str(receipt)] = sha(receipt)
            records[key] = {'case': cases[key], 'terminal': True, 'pass': True,
                            'reused': True, 'independent_receipt': str(receipt),
                            'independent_receipt_sha256': sha(receipt)}
    for name in ('watch_loaded_macro_reset_aligned.py', 'verify_loaded_reset_aligned_terminal.py'):
        path = here / name
        pins[str(path)] = sha(path)
    verify(pins)
    pending = sorted((key for key in cases if key not in records), key=lambda key: priority(cases[key]))
    selected = pending[:args.max_new_checks]
    assert all(permitted(cases[key], requirements) for key in selected)
    assert {cases[key]['mode_mhz'] for key in selected} == {250, 300, 400}
    # Explicit negative control: off-nominal case cannot enter the queue.
    negative = dict(cases[selected[0]], supply_v=1.62)
    assert not permitted(negative, requirements)
    output.mkdir(parents=True)
    plan = {'prepared_nominal_cases': 300, 'reused_independent_passes': len(records),
            'new_batch': selected, 'deferred_cases': len(pending) - len(selected),
            'workers': args.workers, 'per_check_seconds': 43200,
            'off_nominal_negative_control_rejected': True,
            'sha256': pins, 'release_qualified': False,
            'scope': 'Bounded nominal-only reset-interface batch. FixedRC and ideal committed controls. The 300-case matrix is a strategy, not a mandated native count. No wholePLL, MTBF, acquisition or release qualification.'}
    save(output / 'plan.json', plan)
    if args.validate_only:
        print(json.dumps({k:v for k,v in plan.items() if k != 'sha256'}), flush=True)
        return
    lock = threading.Lock()

    def status():
        save(output / 'status.json', {'observed_utc': datetime.now(timezone.utc).isoformat(),
             'cases': records, 'batch_cases': selected,
             'batch_terminal': sum(records.get(key, {}).get('terminal', False) for key in selected),
             'batch_passing': sum(records.get(key, {}).get('pass', False) for key in selected),
             'nominal_passing': sum(record.get('pass', False) for record in records.values()),
             'deferred_cases': plan['deferred_cases'], 'release_qualified': False})

    def run(key):
        case = cases[key]
        deadline = time.monotonic() + 43200
        directory = output / key
        directory.mkdir()
        source = Path(case['directory']) / 'loaded.cir'
        assert permitted(case, requirements) and sha(source) == case['deck_sha256']
        circuit = directory / 'loaded.cir'
        shutil.copyfile(source, circuit)
        manifest = directory / 'input_manifest.json'
        case_pins = dict(pins)
        case_pins[str(circuit)] = sha(circuit)
        pvt = {k:case[k] for k in ('corner', 'supply_v', 'temperature_c')}
        save(manifest, {'sha256': case_pins, 'pvt': pvt, 'mode_mhz': case['mode_mhz'],
             'phase_ps': case['phase_ps'], 'edge_ps': case['edge_ps'],
             'withdrawal_start_ns': case['withdrawal_start_ns'], 'scope': plan['scope']})
        with lock:
            records[key] = {'case':case, 'terminal':False, 'directory':str(directory)}
            status()
        print('Started ' + key, flush=True)
        code = command(['/opt/xyce/bin/Xyce','-linsolv','KLU','-quiet','-o',str(directory/'loaded'),str(circuit)],
                       directory/'run.log', deadline)
        wave = directory/'loaded.prn'
        complete = code == 0 and wave.exists() and 'End of Xyce(TM) Simulation' in wave.read_text()
        save(directory/'assessment.json', {'withdrawal_start_ns':case['withdrawal_start_ns'],
             'simulation_time_ns':case['simulation_time_ns'], 'pvt':pvt, 'mode_mhz':case['mode_mhz'],
             'exit_code':code, 'simulation_completed':complete, 'input_manifest_sha256':sha(manifest),
             'sha256':{str(p):sha(p) for p in [circuit,directory/'run.log',wave] if p.exists()},
             'release_qualified':False, 'functional_audit_pending':complete})
        checks = output/(key+'_terminal_checks')
        receipt = output/(key+'_independent.json')
        audit_code = independent_code = None
        if complete:
            flags = ['--mode-mhz',str(case['mode_mhz']),'--withdraw-start-ns',str(case['withdrawal_start_ns'])]
            audit_code = command([sys.executable,str(here/'watch_loaded_macro_reset_aligned.py'),
                 '--directory',str(directory),'--output',str(checks),*flags], output/(key+'_audit.log'), deadline)
            if audit_code == 0:
                independent_code = command([sys.executable,str(here/'verify_loaded_reset_aligned_terminal.py'),
                    '--directory',str(checks),'--output',str(receipt),*flags], output/(key+'_independent.log'), deadline)
        passed = independent_code == 0 and receipt.exists() and json.loads(receipt.read_text())['pass']
        with lock:
            records[key].update(terminal=True, native_exit_code=code, audit_exit_code=audit_code,
                independent_exit_code=independent_code, **{'pass':passed},
                outcome='PASS' if passed else ('TIMEOUT' if 124 in (code,audit_code,independent_code) else 'NONPASS'))
            if passed:
                records[key].update(independent_receipt=str(receipt), independent_receipt_sha256=sha(receipt))
            status()
        print(f'Terminal {key}: {passed}', flush=True)

    status()
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        for future in concurrent.futures.as_completed([pool.submit(run,key) for key in selected]):
            future.result()
    verify(pins)
    status()


if __name__ == '__main__':
    main()
