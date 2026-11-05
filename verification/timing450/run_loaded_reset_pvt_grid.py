#!/usr/bin/env python3
"""Run and audit the prepared 180-case loaded reset grid, reusing existing pilots."""
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
    prepared = root/'receiver_loaded_reset_pvt_grid_prepared_001'
    output = root/'receiver_loaded_reset_pvt_grid_native_001'
    assert not output.exists()
    recipe_path = prepared/'preparation.json'
    recipe = json.loads(recipe_path.read_text())
    audit_path = root/'receiver_loaded_reset_pvt_grid_deck_audit_001.json'
    audit = json.loads(audit_path.read_text())
    assert audit['pass'] and audit['independently_compared_decks']==180
    assert recipe['prepared_case_count']==180
    verify(audit['sha256'])
    pins = dict(recipe['source_sha256'])
    here = Path(__file__).resolve().parent
    helpers = [here/name for name in ('run_loaded_reset_pvt_grid.py',
               'watch_loaded_macro_reset_pvt.py','audit_loaded_macro_reset_pvt_native.py',
               'replay_loaded_macro_reset.py','audit_loaded_macro_reset_replay.py',
               'audit_receiver_reset_replay.py','characterize_bbpd.py')]
    for path in [recipe_path,audit_path,*helpers,Path('/opt/xyce/bin/Xyce')]:
        pins[str(path)] = sha(path)
    verify(pins)
    # These cases already have native jobs/evidence. Never rerun them here.
    reuse = {('ss',1.62,125,250,20):'receiver_loaded_macro_reset_ss125',
             ('ss',1.62,125,-250,20):'receiver_loaded_macro_reset_ss125_dn',
             ('ff',1.95,-40,250,20):'receiver_loaded_macro_reset_ff195_cold_up'}
    output.mkdir()
    records = {}
    lock = threading.Lock()

    def key(case):
        return tuple(case[k] for k in ('corner','supply_v','temperature_c','phase_ps','edge_ps'))

    def save():
        data = {'cases':records,'prepared_case_count':180,'new_native_case_count':177,
                'reused_native_case_count':3,'workers':2,'source_pins':pins,
                'release_qualified':False,'selected':False,
                'scope':recipe['scope'],'campaign_complete':len(records)==180 and
                all(r.get('terminal',False) for r in records.values())}
        temporary = output/'status.tmp'
        temporary.write_text(json.dumps(data,indent=2)+'\n')
        temporary.replace(output/'status.json')

    pending = []
    for case in recipe['prepared_cases']:
        name = Path(case['directory']).name
        if key(case) in reuse:
            external = root/reuse[key(case)]
            expected=(Path(case['directory'])/'loaded.cir').read_text()
            actual=(external/'loaded.cir').read_text()
            expected_include=next(line for line in expected.splitlines() if line.startswith('.include ') and 'receiver.spice' in line)
            actual_include=next(line for line in actual.splitlines() if line.startswith('.include ') and 'receiver.spice' in line)
            expected_fixture=Path(re.search(r'"(.*?)"',expected_include)[1])
            actual_fixture=Path(re.search(r'"(.*?)"',actual_include)[1])
            assert expected_fixture.read_bytes()==actual_fixture.read_bytes()
            assert actual.replace(actual_include,expected_include)==expected
            for p in (external/'loaded.cir',external/'input_manifest.json',actual_fixture):
                pins[str(p)]=sha(p)
            checks = root/(external.name+'_terminal_checks')/'assessment.json'
            records[name] = {'reuse_directory':str(external),'case':case,
                             'terminal':False,'external_terminal_audit':str(checks)}
            if checks.exists():
                assessed=json.loads(checks.read_text())
                records[name].update(terminal=True,terminal_checks_pass=assessed['terminal_checks_pass'],
                                     external_terminal_audit_sha256=sha(checks))
        else:
            pending.append(case)
    # Exercise both new SS hot slow-edge cases first.
    pending.sort(key=lambda c: (not(c['corner']=='ss' and c['supply_v']==1.62 and
                                   c['temperature_c']==125 and c['edge_ps']==200),key(c)))
    save()

    def run(case):
        name = Path(case['directory']).name
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
        manifest.write_text(json.dumps({'sha256':case_pins,'pvt':pvt,
                                       'phase_ps':case['phase_ps'],'edge_ps':case['edge_ps'],
                                       'scope':recipe['scope']},indent=2)+'\n')
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
        report={'pvt':pvt,'exit_code':code,'simulation_completed':completed,
                'input_manifest_sha256':sha(manifest),
                'sha256':{str(p):sha(p) for p in (circuit,directory/'run.log',wave) if p.exists()},
                'release_qualified':False,'selected':False,'functional_audit_pending':True}
        (directory/'assessment.json').write_text(json.dumps(report,indent=2)+'\n')
        checks=output/(name+'_terminal_checks')
        with (output/(name+'_audit.log')).open('w') as stream:
            result=subprocess.run([sys.executable,str(here/'watch_loaded_macro_reset_pvt.py'),
                                   '--directory',str(directory),'--output',str(checks)],
                                  stdout=stream,stderr=subprocess.STDOUT)
        assessed_path=checks/'assessment.json'
        assessed=json.loads(assessed_path.read_text()) if assessed_path.exists() else {}
        with lock:
            records[name].update(terminal=True,native_complete=completed,audit_exit_code=result.returncode,
                                 terminal_checks_pass=assessed.get('terminal_checks_pass',False))
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
