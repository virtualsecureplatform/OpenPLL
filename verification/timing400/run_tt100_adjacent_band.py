#!/usr/bin/env python3
"""Measure coarse14 beside the completed TT100 coarse13 band, once per endpoint.

Change only the next coarse thermometer bit in an exact completed80ns deck.
Keep native solver, reset, fine encoding and PVT. Atomic retired-dispatch
admission limits the workspace to four native analog jobs. Queue, preparation,
execution and assessment share one12h budget. No identical retry or model adoption.
"""
import argparse
from datetime import datetime,timezone
from decimal import Decimal
import fcntl
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import time
from audit_dco_settling_windows import independent_edges
from benchmark_dco_linear_solver_v2 import waveform
from characterize_compact_propagation import XYCE
from guarded_native_admission import scan
from run_dco_duration_probe_v3 import decimal_measure
from run_dco_qualification import ROOT,sha,save,measure


def main():
    began=time.clock_gettime(time.CLOCK_BOOTTIME);deadline=began+43200
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--fine',required=True,type=int,choices=[8,247]);parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();base=ROOT/'build/timing400/release_001';out=args.output.resolve()
    gate=base/'tt100_endpoint_collection_001/assessment.json';g=json.loads(gate.read_text());assert g['both_native_endpoints_collected'] and not g['intrinsic_tt100_ordered_range_brackets_target']
    original=base/f'dco/n160_tt_27_c13_f{args.fine}_baseline';stem=original/f'dco_postlayout_tt_coarse_13_code_{args.fine:03d}'
    side=stem.with_suffix('.provenance.json');p=json.loads(side.read_text());assert p['completed']
    params=p['parameters'];assert params['vdd']==1.8 and params['corner']=='tt' and params['temperature_c']==27 and params['sim_time_ns']==80 and params['coarse_codes']=='13' and int(params['codes'])==args.fine
    old=stem.with_suffix('.spice');assert sha(old)==p['netlist_sha256'];text=old.read_text()
    before='VCOARSETHERM13 COARSETHERMAL_CODE[13] 0 0';after='VCOARSETHERM13 COARSETHERMAL_CODE[13] 0 {VDD}'
    assert text.count(before)==1;changed=text.replace(before,after).replace('coarse_code=13','coarse_code=14')
    coarse={int(a):b for a,b in re.findall(r'^VCOARSETHERM(\d+) COARSETHERMAL_CODE\[\d+\] 0 (\{VDD\}|0)$',changed,re.M)}
    fine={int(a):b for a,b in re.findall(r'^VCTRL(\d+) DCO_THERM\[\d+\] 0 (\{VDD\}|0)$',changed,re.M)}
    assert set(coarse)==set(range(47)) and all(v==('{VDD}' if i<14 else '0') for i,v in coarse.items())
    assert set(fine)==set(range(255)) and all(v==('0' if i<args.fine else '{VDD}') for i,v in fine.items())
    assert '.tran 10.0p 80.0n 0 10.0p' in changed or '.tran 10.0p 80n 0 10.0p' in changed
    handoff=base/'tt100_range_priority_handoff_001/assessment.json';assert handoff.exists()
    for pid in [3785484,3867630]:
        proc=Path('/proc')/str(pid);assert not proc.exists() or (proc/'stat').read_text().rsplit(')',1)[1].split()[0]=='Z'
    out.mkdir(parents=True,exist_ok=False);deck=out/'range.spice';deck.write_text(changed)
    save(out/'owner.json',dict(runner_pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),budget_started_boottime=began,
        absolute_deadline_uptime=deadline,total_budget_s=43200,includes_admission_and_assessment=True,automatic_identical_retry=False))
    files=[Path(__file__).resolve(),Path(__file__).with_name('guarded_native_admission.py'),XYCE,gate,handoff,old,side,deck,
        Path(__file__).with_name('audit_dco_settling_windows.py'),Path(__file__).with_name('run_dco_duration_probe_v3.py'),ROOT/'scripts/dco_calibration.py']
    pins={**p['files'],**{str(f):sha(f) for f in files}}
    for path,d in pins.items():assert sha(path)==d,path
    save(out/'input_manifest.json',dict(input_sha256=pins,original_coarse=13,measured_coarse=14,fine=args.fine,
        only_coarse_bit13_and_comments_changed=True,coarse_active_high=True,fine_active_low=True,stop_ns=80,
        pvt=dict(corner='tt',temperature_c=27,supply_v=1.8),declared_windows_ns=[[x,80] for x in [20,30,40,50,60]],scope=__doc__))
    def remaining():
        left=deadline-time.clock_gettime(time.CLOCK_BOOTTIME)
        if left<=0:raise TimeoutError('12h total endpoint budget exhausted')
        return left
    def status(state,**fields):save(out/'status.json',dict(state=state,observed_utc=datetime.now(timezone.utc).isoformat(),remaining_s=max(0,deadline-time.clock_gettime(time.CLOCK_BOOTTIME)),release_qualified=False,**fields))
    child=None
    try:
        with (out/'run.log').open('x') as log:
            while child is None:
                remaining()
                with (ROOT/'build/timing400/guarded_native_admission.lock').open('a') as lock:
                    try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
                    except BlockingIOError:pass
                    else:
                        native=scan()
                        if len(native)<4:
                            command=[str(XYCE),'-linsolv','KLU','-quiet','-o',str(out/'range'),str(deck)]
                            child=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,
                                env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1'),start_new_session=True)
                            until=time.monotonic()+2
                            while child.poll() is None and not any(r['pid']==child.pid for r in scan()):
                                assert time.monotonic()<until;time.sleep(.01)
                            native_after=scan();assert len(native_after)<=4
                            save(out/'launch.json',dict(pid=child.pid,command=command,native_before=native,native_after=native_after,absolute_deadline_uptime=deadline))
                if child is None:status('waiting_for_native_capacity');time.sleep(min(30,remaining()))
            status('native_running',native_pid=child.pid);code=child.wait(timeout=remaining())
        save(out/'native_completion.json',dict(exit_code=code,absolute_deadline_uptime=deadline,release_qualified=False))
        if code:status('native_nonpass',exit_code=code);return
        status('assessing_terminal_waveform');wave=out/'range.prn';times,values=waveform(wave);assert times[-1]>=80e-9-1e-15
        edges=independent_edges(wave);records=[]
        for start in [20,30,40,50,60]:
            remaining();row=dict(start_ns=start,stop_ns=80)
            try:
                metric=measure(wave,start,80,1.8,min_periods=3);freq,drift=decimal_measure(edges,start,80)
                assert abs(float(freq)-metric['mhz'])<1e-8 and abs(float(drift)-metric['half_window_difference_mhz'])<1e-8
                row.update(state='measured',**metric,independent_decimal_frequency_mhz=str(freq),independent_decimal_half_window_difference_mhz=str(drift))
            except (ValueError,AssertionError,IndexError) as error:row.update(state='window_unmeasurable',reason=repr(error))
            records.append(row)
        metric=measure(wave,20,80,1.8,min_periods=3)
        for path,d in pins.items():assert sha(path)==d,path
        remaining();save(out/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in out.iterdir() if p.is_file() and p.name!='status.json'},
            native_waveform_terminal=True,metric=metric,records=records,all_declared_windows_retained=True,coarse=14,fine=args.fine,
            range_observation_only=True,calibration_model_qualified=False,release_qualified=False,adopted=False,scope=__doc__))
        status('terminal_range_observation',mhz=metric['mhz']);print('TTcoarse14 fine',args.fine,metric['mhz'],'MHz',flush=True)
    except (TimeoutError,subprocess.TimeoutExpired):
        if child is not None and child.poll() is None:
            os.killpg(child.pid,signal.SIGTERM)
            try:child.wait(timeout=10)
            except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
        status('timeout_inconclusive')

if __name__=='__main__':main()
