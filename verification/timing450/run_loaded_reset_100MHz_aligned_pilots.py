#!/usr/bin/env python3
"""Run two corrected100MHz loaded-reset pilots with explicit207nswithdrawal audits."""
import concurrent.futures
import json
import re
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from characterize_bbpd import sha, verify


def main():
    root = Path('build/timing450/interface_characterization').resolve()
    prepared = root/'receiver_loaded_reset_100MHz_aligned_prepared_001'
    output = root/'receiver_loaded_reset_100MHz_aligned_pilots_001'
    assert not output.exists()
    recipe_path = prepared/'preparation.json'
    recipe = json.loads(recipe_path.read_text())
    audit_path = root/'receiver_loaded_reset_100MHz_aligned_deck_audit_001.json'
    audit = json.loads(audit_path.read_text())
    assert audit['deck_preparation_audit_pass'] and audit['prepared_cases']==180
    assert recipe['prepared_case_count']==180
    verify(audit['sha256'])
    native_validation = root/'receiver_loaded_macro_reset_ss125_aligned_watcher_validation_001/native_audit.json'
    watcher_validation = root/'receiver_loaded_macro_reset_ss125_aligned_watcher_validation_001/assessment.json'
    native_check = json.loads(native_validation.read_text())
    terminal_check = json.loads(watcher_validation.read_text())
    assert native_check['native_complete_wave_audit_pass'] and native_check['mode_mhz']==450
    assert terminal_check['terminal_checks_pass'] and terminal_check['mode_mhz']==450
    verify(native_check['sha256'])
    verify(terminal_check['source_pins'])
    independent_validation = root/'receiver_loaded_macro_reset_ss125_aligned_independent_terminal_001.json'
    independent_check = json.loads(independent_validation.read_text())
    assert independent_check['pass'] and independent_check['mode_mhz']==450 and independent_check['withdrawal_start_ns']==187.05
    assert independent_check['pll_edges_independently_verified']==315
    verify(independent_check['sha256'])
    profile_control = root/'receiver_loaded_reset_aligned_wrong_profile_control_001.json'
    control = json.loads(profile_control.read_text())
    assert control['negative_control_rejected'] and control['corrected_profile_input_accepted']
    verify(control['sha256'])
    pins = dict(recipe['source_sha256'])
    here = Path(__file__).resolve().parent
    helpers = [here/name for name in ('run_loaded_reset_100MHz_aligned_pilots.py',
               'watch_loaded_macro_reset_aligned.py','audit_loaded_macro_reset_aligned_native.py',
               'replay_loaded_macro_reset_aligned.py','audit_loaded_macro_reset_aligned_replay.py',
               'audit_receiver_reset_replay.py','characterize_bbpd.py','loaded_reset_withdrawal_profile.py','verify_loaded_reset_aligned_terminal.py')]
    for path in [recipe_path,audit_path,native_validation,watcher_validation,independent_validation,profile_control,*helpers,Path('/opt/xyce/bin/Xyce')]:
        pins[str(path)] = sha(path)
    verify(pins)
    output.mkdir()
    records = {}
    lock = threading.Lock()
    pending = [case for case in recipe['prepared_cases']
               if case['mode_mhz'] == 100 and case['corner']=='ss'
               and case['supply_v']==1.62 and case['temperature_c']==125 and case['edge_ps']==20]
    assert len(pending)==2
    pending.sort(key=lambda c:(c['mode_mhz'],c['phase_ps']))
    scope = 'Two corrected100MHzSS1.62V/125C signed-phase20ps loaded-reset pilots withdrawing at207.05ns. Same physical circuit/RC/clocks; full-clock strict native/replay/consumption/direction-control and independent audits. Loaded condition must be observed; no fullPVT/MTBF/acquisition/wholePLL/release qualification.'

    def save():
        data = {'cases':records,'pilot_case_count':2,'workers':2,'source_pins':pins,
                'release_qualified':False,'selected':False,'scope':scope,
                'campaign_complete':len(records)==2 and all(r.get('terminal',False) for r in records.values())}
        temporary = output/'status.tmp'
        temporary.write_text(json.dumps(data,indent=2)+'\n')
        temporary.replace(output/'status.json')
    save()

    def run(case):
        name = f"{case['mode_mhz']}MHz_"+Path(case['directory']).name
        assert case['withdrawal_start_ns']==207.05 and case['mode_mhz']==100
        source = Path(case['directory'])/'loaded.cir'
        assert sha(source)==case['deck_sha256']
        directory = output/name
        directory.mkdir()
        circuit = directory/'loaded.cir'
        shutil.copyfile(source,circuit)
        case_pins = dict(pins)
        for p in [source,circuit]: case_pins[str(p)]=sha(p)
        pvt={k:case[k] for k in ('corner','supply_v','temperature_c')}
        manifest=directory/'input_manifest.json'
        manifest.write_text(json.dumps({'sha256':case_pins,'pvt':pvt,'mode_mhz':case['mode_mhz'],
                                       'phase_ps':case['phase_ps'],'edge_ps':case['edge_ps'],'withdrawal_start_ns':case['withdrawal_start_ns'],
                                       'scope':scope},indent=2)+'\n')
        command=['/opt/xyce/bin/Xyce','-linsolv','KLU','-quiet','-o',str(directory/'loaded'),str(circuit)]
        with (directory/'run.log').open('w') as stream:
            process=subprocess.Popen(command,stdout=stream,stderr=subprocess.STDOUT)
            with lock:
                records[name]={'case':case,'directory':str(directory),'native_pid':process.pid,'terminal':False}
                save()
            print(f'Started {name} PID {process.pid}',flush=True)
            code=process.wait()
        wave=directory/'loaded.prn'
        log=(directory/'run.log').read_text()
        completed=code==0 and wave.exists() and 'End of Xyce(TM) Simulation' in wave.read_text() and not any(s in log for s in ('Unrecognized dot line','Simulation aborted','Netlist error'))
        report={'withdrawal_start_ns':case['withdrawal_start_ns'],'simulation_time_ns':450,'pvt':pvt,'mode_mhz':case['mode_mhz'],'exit_code':code,'simulation_completed':completed,
                'input_manifest_sha256':sha(manifest),
                'sha256':{str(p):sha(p) for p in (circuit,directory/'run.log',wave) if p.exists()},
                'release_qualified':False,'selected':False,'functional_audit_pending':True}
        (directory/'assessment.json').write_text(json.dumps(report,indent=2)+'\n')
        checks=output/(name+'_terminal_checks')
        with (output/(name+'_audit.log')).open('w') as stream:
            result=subprocess.run([sys.executable,str(here/'watch_loaded_macro_reset_aligned.py'),
                                   '--directory',str(directory),'--output',str(checks),'--mode-mhz',str(case['mode_mhz']),'--withdraw-start-ns',str(case['withdrawal_start_ns'])],
                                  stdout=stream,stderr=subprocess.STDOUT)
        assessed_path=checks/'assessment.json'
        assessed=json.loads(assessed_path.read_text()) if assessed_path.exists() else {}
        independent_path=output/(name+'_independent.json')
        independent_log=output/(name+'_independent.log')
        with independent_log.open('w') as stream:
            independent_result=subprocess.run([sys.executable,str(here/'verify_loaded_reset_aligned_terminal.py'),
                '--directory',str(checks),'--output',str(independent_path),'--mode-mhz',str(case['mode_mhz']),
                '--withdraw-start-ns',str(case['withdrawal_start_ns'])],stdout=stream,stderr=subprocess.STDOUT)
        independent=json.loads(independent_path.read_text()) if independent_path.exists() else {}
        with lock:
            records[name].update(terminal=True,native_complete=completed,audit_exit_code=result.returncode,
                                 terminal_checks_pass=assessed.get('terminal_checks_pass',False))
            records[name].update(independent_verifier_exit_code=independent_result.returncode,
                independent_verification_pass=independent_result.returncode==0 and independent.get('pass',False),
                independent_log_sha256=sha(independent_log))
            if independent_path.exists():records[name]['independent_assessment_sha256']=sha(independent_path)
            if assessed_path.exists():records[name]['terminal_audit_sha256']=sha(assessed_path)
            save()
        print(f'Terminal {name}: {records[name]["terminal_checks_pass"]}',flush=True)

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        for future in concurrent.futures.as_completed([pool.submit(run,c) for c in pending]):
            future.result()
    verify(pins)
    save()


if __name__=='__main__':
    main()
