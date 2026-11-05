#!/usr/bin/env python3
"""Run the audited720 lower-mode loaded-reset cases, reusing eight qualified pilots."""
import argparse
import concurrent.futures
import json
import shutil
import subprocess
import sys
import threading
from itertools import product
from pathlib import Path
from characterize_bbpd import sha, verify
from loaded_reset_withdrawal_profile import validate_withdrawal


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--validate-only',action='store_true')
    args=parser.parse_args()
    root=Path('build/timing450/interface_characterization').resolve()
    output=root/'receiver_loaded_reset_remaining_modes_native_001'
    validation_path=root/'receiver_loaded_reset_remaining_modes_launch_validation_001.json'
    assert not output.exists()
    recipe_path=root/'receiver_loaded_reset_remaining_modes_prepared_001/preparation.json'
    audit_path=root/'receiver_loaded_reset_remaining_modes_deck_audit_001.json'
    recipe=json.loads(recipe_path.read_text());audit=json.loads(audit_path.read_text())
    assert recipe['prepared_case_count']==720 and audit['preparation_audit_pass']
    assert audit['independently_compared_decks']==720 and audit['exact_mode_PVT_phase_edge_coverage_verified']
    here=Path(__file__).resolve().parent
    pins={}
    def merge(mapping):
        for p,digest in mapping.items():
            assert p not in pins or pins[p]==digest, f'Conflicting pinned artifact: {p}'
            pins[p]=digest
    merge(recipe['source_sha256']);merge(audit['sha256'])
    helpers=[here/name for name in ('run_loaded_reset_remaining_modes.py',
        'watch_loaded_macro_reset_aligned.py','audit_loaded_macro_reset_aligned_native.py',
        'replay_loaded_macro_reset_aligned.py','audit_loaded_macro_reset_aligned_replay.py',
        'audit_receiver_reset_replay.py','characterize_bbpd.py','loaded_reset_withdrawal_profile.py',
        'verify_loaded_reset_aligned_terminal.py')]
    for p in [recipe_path,audit_path,*helpers,Path('/opt/xyce/bin/Xyce')]:pins[str(p)]=sha(p)
    scope='720 deterministic lower-mode loaded-reset cases: corrected100MHz207.05ns withdrawal;250/300/400MHz187.05ns withdrawal. Fixed nominal cellRC/max routeRC and ideal committed controls. Reuses eight independently verified pilots; retains all failures. No MTBF/full acquisition/wholePLL/release qualification.'
    records={};pending=[];seen=set();reuse=[]
    for case in recipe['prepared_cases']:
        key=tuple(case[k] for k in ('mode_mhz','corner','supply_v','temperature_c','phase_ps','edge_ps'))
        assert key not in seen;seen.add(key)
        assert case['simulation_time_ns']==450
        assert case['withdrawal_start_ns']==(207.05 if case['mode_mhz']==100 else 187.05)
        deck=Path(case['directory'])/'loaded.cir'
        assert sha(deck)==case['deck_sha256']
        validate_withdrawal(deck.read_text(),case['mode_mhz'],case['withdrawal_start_ns'],case)
        name=f"{case['mode_mhz']}MHz_"+Path(case['directory']).name
        is_pilot=case['corner']=='ss' and case['supply_v']==1.62 and case['temperature_c']==125 and case['edge_ps']==20
        if not is_pilot:
            pending.append(case);continue
        revised=case['mode_mhz']==100
        original=root/('receiver_loaded_reset_100MHz_aligned_pilots_001' if revised else 'receiver_loaded_reset_lower_mode_pilots_001')/name
        checks=original.parent/(name+'_terminal_checks')
        independent_path=(original.parent if revised else root/'receiver_loaded_reset_campaign_independent_terminals_001')/(name+'_independent.json')
        independent=json.loads(independent_path.read_text());terminal=json.loads((checks/'assessment.json').read_text())
        assert independent['pass'] and independent['mode_mhz']==case['mode_mhz'] and independent['simulation_time_ns']==450
        assert independent['pvt']=={'corner':case['corner'],'supply_v':case['supply_v'],'temperature_c':case['temperature_c']}
        consumption=independent['consumption']
        assert consumption['phase_ps']==case['phase_ps'] and consumption['physical_storage_loaded_before_withdrawal']
        assert len(consumption['pre_withdrawal_consumed_events'])==1 and len(consumption['fresh_events'])==1
        assert not consumption['stale_events_after_reset_before_next_ref'] and not consumption['opposite_events']
        assert terminal['terminal_checks_pass'] and terminal['direction_control_rejected']
        assert (original/'loaded.cir').read_bytes()==deck.read_bytes()
        if revised:assert independent['withdrawal_start_ns']==207.05
        merge(independent['sha256'])
        for p in [independent_path,checks/'assessment.json',deck]:pins[str(p)]=sha(p)
        records[name]={'case':case,'directory':str(original),'terminal':True,'reused':True,
            'native_complete':True,'terminal_checks_pass':True,'independent_verification_pass':True,
            'independent_receipt':str(independent_path),'independent_assessment_sha256':sha(independent_path)}
        reuse.append(name)
    assert seen==set(product((100,250,300,400),('tt','ff','ss','sf','fs'),(1.62,1.8,1.95),(-40,27,125),(-250,250),(20,200)))
    assert len(reuse)==8 and len(pending)==712
    verify(pins)
    validation={'pass':True,'prepared_cases':720,'reused_independent_pilots':reuse,'new_native_cases':712,
        'workers':4,'sha256':pins,'scope':scope,'native_simulation_launched':False,'release_qualified':False,'selected':False}
    if args.validate_only:
        assert not validation_path.exists()
        validation_path.write_text(json.dumps(validation,indent=2)+'\n')
        print(json.dumps({k:v for k,v in validation.items() if k!='sha256'}),flush=True)
        return
    frozen=json.loads(validation_path.read_text())
    assert frozen==validation
    pins[str(validation_path)]=sha(validation_path)
    output.mkdir()
    lock=threading.Lock()
    def save():
        terminal=[r for r in records.values() if r.get('terminal',False)]
        data={'cases':records,'prepared_case_count':720,'reused_case_count':8,'new_native_case_count':712,
            'workers':4,'source_pins':pins,'terminal_cases':len(terminal),
            'passing_cases':sum(bool(r.get('terminal_checks_pass') and r.get('independent_verification_pass')) for r in terminal),
            'campaign_complete':len(terminal)==720,'scope':scope,'release_qualified':False,'selected':False}
        temporary=output/'status.tmp';temporary.write_text(json.dumps(data,indent=2)+'\n');temporary.replace(output/'status.json')
    save()
    def run(case):
        name = f"{case['mode_mhz']}MHz_"+Path(case['directory']).name
        assert case['withdrawal_start_ns']==(207.05 if case['mode_mhz']==100 else 187.05)
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

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for future in concurrent.futures.as_completed([pool.submit(run,c) for c in pending]):
            future.result()
    verify(pins)
    save()


if __name__=='__main__':
    main()
