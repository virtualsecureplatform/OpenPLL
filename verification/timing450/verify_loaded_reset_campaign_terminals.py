#!/usr/bin/env python3
"""Independently verify existing reset campaign receipts; never run analog."""
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from characterize_bbpd import sha, verify


def main():
    root = Path('build/timing450/interface_characterization').resolve()
    here = Path(__file__).resolve().parent
    helper = here / 'verify_loaded_reset_modes_terminal.py'
    output = root / 'receiver_loaded_reset_campaign_independent_terminals_001'
    assert not output.exists()
    prepared = root / 'receiver_loaded_reset_pvt_grid_prepared_001/preparation.json'
    all_modes = root / 'receiver_loaded_reset_all_modes_prepared_001/preparation.json'
    regression_path = root / 'receiver_loaded_reset_full_clock_regression_001.json'
    validated_path = root / 'receiver_loaded_macro_reset_ss125_modes_independent_terminal_001.json'
    control_path = root / 'receiver_loaded_reset_modes_wrong_mode_control_001/assessment.json'
    recipe, modes, regression, validated, control = [json.loads(p.read_text()) for p in
        (prepared, all_modes, regression_path, validated_path, control_path)]
    assert recipe['prepared_case_count'] == 180 and modes['prepared_case_count'] == 900
    assert regression['pass'] and validated['pass'] and validated['mode_mhz'] == 450
    assert control['negative_control_rejected']
    pins = {}
    for mapping in (recipe['source_sha256'], modes['source_sha256'], regression['sha256'],
                    validated['sha256'], control['sha256']):
        for path, digest in mapping.items():
            assert path not in pins or pins[path] == digest
            pins[path] = digest
    for path in (prepared, all_modes, regression_path, validated_path, control_path,
                 helper, Path(__file__).resolve(), here / 'characterize_bbpd.py'):
        assert str(path) not in pins or pins[str(path)] == sha(path)
        pins[str(path)] = sha(path)
    verify(pins)
    output.mkdir()
    cases, records = {}, {}
    reused = {('ss', 1.62, 125, 250, 20): ('receiver_loaded_macro_reset_ss125', 'UP'),
              ('ss', 1.62, 125, -250, 20): ('receiver_loaded_macro_reset_ss125_dn', 'DN')}
    external = {('ff', 1.95, -40, 250, 20): 'receiver_loaded_macro_reset_ff195_cold_up'}
    for case in recipe['prepared_cases']:
        stem = Path(case['directory']).name
        name = '450MHz_' + stem
        key = tuple(case[k] for k in ('corner', 'supply_v', 'temperature_c', 'phase_ps', 'edge_ps'))
        if key in reused:
            native, direction = reused[key]
            cases[name] = (dict(case, mode_mhz=450), root/native, None)
            assert regression['records'][direction]['pass']
            records[name] = {'mode_mhz': 450, 'terminal': True, 'independent_verification_pass': True,
                             'reused_regression': str(regression_path),
                             'regression_sha256': sha(regression_path)}
        else:
            native = root/external[key] if key in external else root/'receiver_loaded_reset_pvt_grid_native_001'/stem
            checks = root/'receiver_loaded_reset_full_clock_grid_reaudits_001'/(stem+'_terminal_checks')
            cases[name] = (dict(case, mode_mhz=450), native, checks)
            records[name] = {'mode_mhz': 450, 'terminal': False, 'native_directory': str(native),
                             'terminal_directory': str(checks)}
    lower = [case for case in modes['prepared_cases'] if case['mode_mhz'] != 450 and
             (case['corner'], case['supply_v'], case['temperature_c'], case['edge_ps']) == ('ss', 1.62, 125, 20)]
    assert len(lower) == 8
    for case in lower:
        name = f"{case['mode_mhz']}MHz_" + Path(case['directory']).name
        native = root/'receiver_loaded_reset_lower_mode_pilots_001'/name
        checks = native.with_name(name+'_terminal_checks')
        cases[name] = (case, native, checks)
        records[name] = {'mode_mhz': case['mode_mhz'], 'terminal': False,
                         'native_directory': str(native), 'terminal_directory': str(checks)}
    assert len(cases) == len(records) == 188

    def identity(name):
        case, native, _ = cases[name]
        source, actual = Path(case['directory'])/'loaded.cir', native/'loaded.cir'
        assert sha(source) == case['deck_sha256']
        expected, observed = source.read_text(), actual.read_text()
        ei = next(line for line in expected.splitlines() if line.startswith('.include ') and 'receiver.spice' in line)
        ai = next(line for line in observed.splitlines() if line.startswith('.include ') and 'receiver.spice' in line)
        ep, ap = [Path(re.search(r'"(.*?)"', line)[1]) for line in (ei, ai)]
        assert ep.read_bytes() == ap.read_bytes() and observed.replace(ai, ei) == expected
        return {str(path): sha(path) for path in (source, actual, ep, ap)}

    for name in records:
        if records[name]['terminal']:
            records[name]['input_pins'] = identity(name)

    def save():
        terminal = sum(r['terminal'] for r in records.values())
        passed = sum(r.get('independent_verification_pass', False) for r in records.values())
        report = {'expected_cases': 188, 'terminal_cases': terminal, 'passing_cases': passed,
                  'campaign_complete': terminal == 188, 'all_independent_verifications_pass': terminal == passed == 188,
                  'cases': records, 'source_pins': pins, 'launches_native_simulations': False,
                  'release_qualified': False, 'selected': False,
                  'scope': 'Independent verification of180 existing450MHz grid cases and eight lower-modeSS12520ps pilots. '
                           'Remaining712 lower-modePVT/edge cases are outside this queue. FixedRC/ideal committed controls; '
                           'full reset/acquisition/MTBF/wholePLL and release gates remain outstanding.'}
        temporary = output/'status.tmp'
        temporary.write_text(json.dumps(report, indent=2)+'\n')
        temporary.replace(output/'status.json')

    save()
    waiting = {name for name in records if not records[name]['terminal']}
    while waiting:
        for name in sorted(waiting):
            case, native, checks = cases[name]
            receipt = checks/'assessment.json'
            if not receipt.exists():
                continue
            assessed = json.loads(receipt.read_text())
            records[name]['terminal_assessment_sha256'] = sha(receipt)
            records[name]['independent_verification_running'] = True
            save()
            try:
                local_pins = identity(name)
                assert sha(helper) == pins[str(helper)]
                result_path = output/(name+'_independent.json')
                log = output/(name+'_verification.log')
                with log.open('w') as stream:
                    result = subprocess.run([sys.executable, str(helper), '--directory', str(checks),
                        '--mode-mhz', str(case['mode_mhz']), '--output', str(result_path)],
                        stdout=stream, stderr=subprocess.STDOUT)
                verify(local_pins)
                assert sha(receipt) == records[name]['terminal_assessment_sha256']
                verified = json.loads(result_path.read_text()) if result_path.exists() else {}
                passed = result.returncode == 0 and assessed['terminal_checks_pass'] and verified.get('pass', False)
                records[name].update(independent_verification_pass=passed, verifier_exit_code=result.returncode,
                    input_pins=local_pins, verification_log=str(log), verification_log_sha256=sha(log),
                    independent_assessment=str(result_path),
                    independent_assessment_sha256=sha(result_path) if result_path.exists() else None)
            except Exception as error:
                records[name].update(independent_verification_pass=False, verification_exception=repr(error))
            records[name].update(terminal=True, independent_verification_running=False)
            waiting.remove(name)
            save()
            print(f"Independent terminal {name}: {records[name]['independent_verification_pass']}", flush=True)
        if waiting:
            time.sleep(10)
    verify(pins)
    save()


if __name__ == '__main__':
    main()
