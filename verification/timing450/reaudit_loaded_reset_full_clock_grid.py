#!/usr/bin/env python3
"""Re-audit existing grid natives with full-clock replay; never launch analog."""
import concurrent.futures
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from characterize_bbpd import sha, verify


def main():
    root = Path('build/timing450/interface_characterization').resolve()
    prepared = root/'receiver_loaded_reset_pvt_grid_prepared_001/preparation.json'
    recipe = json.loads(prepared.read_text())
    regression_path = root/'receiver_loaded_reset_full_clock_regression_001.json'
    regression = json.loads(regression_path.read_text())
    assert recipe['prepared_case_count']==180 and regression['pass']
    verify(recipe['source_sha256'])
    verify(regression['sha256'])
    output = root/'receiver_loaded_reset_full_clock_grid_reaudits_001'
    assert not output.exists()
    here = Path(__file__).resolve().parent
    helpers = [here/name for name in (Path(__file__).name, 'watch_loaded_macro_reset_modes.py',
               'replay_loaded_macro_reset_modes_v2.py', 'audit_loaded_macro_reset_modes_native.py',
               'audit_loaded_macro_reset_modes_replay.py', 'audit_receiver_reset_replay.py',
               'characterize_bbpd.py')]
    pins = dict(recipe['source_sha256'])
    for path, digest in regression['sha256'].items():
        assert path not in pins or pins[path]==digest
        pins[path] = digest
    for path in [prepared,regression_path,*helpers]:
        pins[str(path)] = sha(path)
    verify(pins)
    output.mkdir()
    records = {}
    cases = {}
    reused = {('ss',1.62,125,250,20):('receiver_loaded_macro_reset_ss125','UP'),
              ('ss',1.62,125,-250,20):('receiver_loaded_macro_reset_ss125_dn','DN')}
    external = {('ff',1.95,-40,250,20):'receiver_loaded_macro_reset_ff195_cold_up'}
    for case in recipe['prepared_cases']:
        key = tuple(case[k] for k in ('corner','supply_v','temperature_c','phase_ps','edge_ps'))
        name = Path(case['directory']).name
        source = Path(case['directory'])/'loaded.cir'
        assert sha(source)==case['deck_sha256']
        if key in reused:
            directory, direction = reused[key]
            assert regression['records'][direction]['pass']
            expected = source.read_text()
            actual = (root/directory/'loaded.cir').read_text()
            ei = next(l for l in expected.splitlines() if l.startswith('.include ') and 'receiver.spice' in l)
            ai = next(l for l in actual.splitlines() if l.startswith('.include ') and 'receiver.spice' in l)
            ep, ap = (Path(re.search(r'"(.*?)"',l)[1]) for l in (ei,ai))
            assert ep.read_bytes()==ap.read_bytes() and actual.replace(ai,ei)==expected
            records[name] = {'native_directory':str(root/directory), 'terminal':True,
                             'terminal_checks_pass':True, 'reused_full_clock_regression':str(regression_path),
                             'native_deck_identity_verified':True,
                             'regression_sha256':sha(regression_path)}
        else:
            directory = (root/external[key] if key in external else
                         root/'receiver_loaded_reset_pvt_grid_native_001'/name)
            records[name] = {'native_directory':str(directory), 'terminal':False}
            cases[name] = (case,directory)
    assert len(records)==180

    def save():
        complete = sum(r['terminal'] for r in records.values())
        passed = sum(r.get('terminal_checks_pass',False) for r in records.values())
        result = {'prepared_case_count':180, 'terminal_cases':complete, 'passing_cases':passed,
                  'campaign_complete':complete==180, 'all_terminal_checks_pass':complete==passed==180,
                  'cases':records, 'source_pins':pins, 'release_qualified':False, 'selected':False,
                  'scope':'Full-clock reaudits of existing450MHz loaded-reset native grid. '
                          'FixedRC/ideal committed boundaries; lower modes, reset generation/acquisition, MTBF and wholePLL remain separate requirements.'}
        temporary = output/'status.tmp'
        temporary.write_text(json.dumps(result,indent=2)+'\n')
        temporary.replace(output/'status.json')

    def audit_case(name):
        case, directory = cases[name]
        source = Path(case['directory'])/'loaded.cir'
        expected, actual = source.read_text(), (directory/'loaded.cir').read_text()
        ei = next(l for l in expected.splitlines() if l.startswith('.include ') and 'receiver.spice' in l)
        ai = next(l for l in actual.splitlines() if l.startswith('.include ') and 'receiver.spice' in l)
        ep, ap = (Path(re.search(r'"(.*?)"',l)[1]) for l in (ei,ai))
        assert ep.read_bytes()==ap.read_bytes() and actual.replace(ai,ei)==expected
        local_pins = {str(p):sha(p) for p in (source,directory/'loaded.cir',directory/'input_manifest.json',ep,ap)}
        verify(pins)
        checks = output/(name+'_terminal_checks')
        with (output/(name+'_audit.log')).open('w') as stream:
            completed = subprocess.run([sys.executable,str(here/'watch_loaded_macro_reset_modes.py'),
                         '--directory',str(directory),'--output',str(checks),'--mode-mhz','450'],
                         stdout=stream,stderr=subprocess.STDOUT)
        receipt = checks/'assessment.json'
        assessed = json.loads(receipt.read_text()) if receipt.exists() else {}
        verify(local_pins)
        return {'terminal':True, 'watcher_exit_code':completed.returncode,
                'terminal_checks_pass':assessed.get('terminal_checks_pass',False),
                'terminal_assessment':str(receipt),
                'terminal_assessment_sha256':sha(receipt) if receipt.exists() else None,
                'native_deck_identity_verified':True,'input_pins':local_pins}

    save()
    waiting = set(cases)
    active = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        while waiting or active:
            for future in list(active):
                if future.done():
                    name = active.pop(future)
                    try:
                        records[name].update(future.result())
                    except Exception as error:
                        records[name].update(terminal=True,terminal_checks_pass=False,audit_exception=repr(error))
                    save()
                    print(f'Terminal full-clock reaudit {name}: {records[name]["terminal_checks_pass"]}',flush=True)
            for name in sorted(waiting):
                if len(active)>=2:
                    break
                receipt = cases[name][1]/'assessment.json'
                if not receipt.exists():
                    continue
                native = json.loads(receipt.read_text())
                # Failed native runs are terminal too; the watcher retains failure.
                assert 'exit_code' in native and 'simulation_completed' in native
                active[pool.submit(audit_case,name)] = name
                waiting.remove(name)
                records[name]['audit_running'] = True
                save()
                print(f'Started full-clock reaudit {name}',flush=True)
            if waiting or active:
                time.sleep(10)
    verify(pins)
    save()


if __name__=='__main__':
    main()
