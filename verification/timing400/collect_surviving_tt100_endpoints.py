#!/usr/bin/env python3
"""Collect the preserved TT100 wrappers after dispatcher retirement, without rerun.

Require natural completed CSV/provenance and terminal native waveforms. Retain
all five declared windows, including unmeasurable short windows at100MHz.
Range observations do not qualify a calibration profile or release model.
"""
import csv
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import time
from audit_dco_settling_windows import independent_edges
from run_dco_duration_probe_v3 import decimal_measure
from run_dco_qualification import ROOT,sha,save,measure


def process(pid):
    path=Path('/proc')/str(pid)
    try:
        fields=(path/'stat').read_text().rsplit(')',1)[1].split()
        return dict(state=fields[0],start_ticks=int(fields[19]),argv=[s.decode() for s in (path/'cmdline').read_bytes().split(b'\0') if s])
    except FileNotFoundError:return None


def main():
    base=ROOT/'build/timing400/release_001';handoff=base/'scheduling_handoff_002/assessment.json'
    h=json.loads(handoff.read_text());assert h['retired_dco_dispatcher']==3785484
    out=base/'tt100_endpoint_collection_001';out.mkdir(exist_ok=False);began=time.clock_gettime(time.CLOCK_BOOTTIME)
    hz=os.sysconf('SC_CLK_TCK');owners=[]
    for row in h['native_after']:
        path=Path(row['output']);assert '_c13_' in str(path)
        parent=process(row['ppid'])
        if parent and parent['state']!='Z':
            assert str(path.parent) in parent['argv'];deadline=parent['start_ticks']/hz+43200
        else:deadline=row['start_ticks']/hz+43200
        owners.append(dict(code=247 if 'f247_' in str(path.parent) else 8,output=str(path),native_pid=row['pid'],
            native_start_ticks=row['start_ticks'],wrapper_pid=row['ppid'],wrapper_identity_at_collection=parent,absolute_deadline_uptime=deadline))
    assert {r['code'] for r in owners}=={8,247}
    save(out/'owner.json',dict(started_utc=datetime.now(timezone.utc).isoformat(),runner_pid=os.getpid(),
        original_native_checks=owners,read_only_collection=True,native_jobs_added=0,total_budget_restarted=False))
    pins={str(p):sha(p) for p in [Path(__file__).resolve(),handoff,ROOT/'scripts/dco_calibration.py',
        Path(__file__).with_name('audit_dco_settling_windows.py'),Path(__file__).with_name('run_dco_duration_probe_v3.py')]}
    cases={};pending=list(owners)
    while pending:
        for owner in list(pending):
            left=owner['absolute_deadline_uptime']-time.clock_gettime(time.CLOCK_BOOTTIME)
            if left<=0:
                save(out/f'f{owner["code"]}.timeout.json',dict(state='timeout_inconclusive',native_jobs_added=0,release_qualified=False));pending.remove(owner);continue
            parent=process(owner['wrapper_pid']);native=process(owner['native_pid'])
            native_live=native and native['state']!='Z' and native['start_ticks']==owner['native_start_ticks']
            parent_live=parent and parent['state']!='Z' and str(Path(owner['output']).parent) in parent['argv']
            if native_live or parent_live:continue
            directory=Path(owner['output']).parent;csvpath=directory/'dco_postlayout_results.csv'
            if not csvpath.exists():
                save(out/f'f{owner["code"]}.nonpass.json',dict(state='wrapper_terminal_without_csv',release_qualified=False));pending.remove(owner);continue
            rows=list(csv.DictReader(csvpath.open()));assert len(rows)==1;row=rows[0]
            assert row['status']=='pass' and row['returncode']=='0' and row['timed_out']=='no'
            assert int(row['coarse_code'])==13 and int(row['code'])==owner['code']
            wave=Path(row['waveform']);side=wave.with_suffix('.provenance.json');r=json.loads(side.read_text());p=r['parameters']
            assert r['completed'] and p['sim_time_ns']==80 and p['meas_start_ns']==20
            assert p['coarse_codes']=='13' and int(p['codes'])==owner['code'] and p['corner']=='tt' and p['temperature_c']==27 and p['vdd']==1.8
            assert p['max_step_ps']==10 and p['xyce_reltol']==1e-5 and p['xyce_abstol']==1e-9 and p['therm_invert']
            assert sha(Path(row['netlist']))==r['netlist_sha256']
            with wave.open('rb') as stream:stream.seek(max(0,wave.stat().st_size-1024));assert b'End of Xyce(TM) Simulation' in stream.read()
            for path,d in r['files'].items():assert path not in pins or pins[path]==d; pins[path]=d
            for file in [wave,side,csvpath,Path(row['netlist']),Path(row['log'])]:pins[str(file)]=sha(file)
            metric=dict(code=owner['code'],**measure(wave,20,80,1.8,min_periods=3),waveform=str(wave),waveform_sha256=sha(wave),reused=False)
            result=out/f'f{owner["code"]}.result.json';save(result,dict(state='native_pass',metric=metric,source_csv=str(csvpath),collected_after_dispatcher_retirement=True,native_jobs_added=0,release_qualified=False))
            edges=independent_edges(wave);windows=[]
            for start in [20,30,40,50,60]:
                item=dict(start_ns=start,stop_ns=80)
                try:
                    m=measure(wave,start,80,1.8,min_periods=3);freq,drift=decimal_measure(edges,start,80)
                    assert abs(float(freq)-m['mhz'])<1e-8 and abs(float(drift)-m['half_window_difference_mhz'])<1e-8
                    item.update(state='measured',**m,decimal_frequency_mhz=str(freq),decimal_half_window_difference_mhz=str(drift),necessary_100ppm_cap_mhz=.01,half_window_drift_below_100ppm=float(drift)<=.01)
                except (ValueError,AssertionError,IndexError) as error:item.update(state='window_unmeasurable',reason=repr(error))
                windows.append(item)
            cases[owner['code']]=dict(metric=metric,windows=windows,result=str(result));pending.remove(owner)
            save(out/'partial_results.json',dict(cases=cases,all_declared_windows_retained=True,release_qualified=False))
            print('Collected TT100 endpoint',owner['code'],metric['mhz'],'MHz without native rerun.',flush=True)
        save(out/'status.json',dict(state='waiting_for_preserved_wrappers' if pending else 'verifying_terminal_inputs',pending_codes=[r['code'] for r in pending],release_qualified=False))
        if pending:time.sleep(min(10,min(r['absolute_deadline_uptime']-time.clock_gettime(time.CLOCK_BOOTTIME) for r in pending)))
    for path,d in pins.items():assert sha(path)==d,path
    both=set(cases)=={8,247};bracket=both and cases[8]['metric']['mhz']<=100<=cases[247]['metric']['mhz']
    save(out/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file() and p.name!='status.json'},
        cases=cases,both_native_endpoints_collected=both,intrinsic_tt100_ordered_range_brackets_target=bool(bracket),
        all_declared_windows_retained=True,native_jobs_added=0,measurement_window_adopted=False,calibration_model_qualified=False,
        loaded_model_qualified=False,release_qualified=False,adopted=False,scope=__doc__))
    save(out/'status.json',dict(state='terminal_collection',range_brackets_target=bool(bracket),release_qualified=False))

if __name__=='__main__':main()
