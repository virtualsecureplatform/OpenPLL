#!/usr/bin/env python3
"""Run the prepared HS diode comparison with one guarded analog slot.

Hold the admission lock through each individual simulator execution so the
ngspice reference cannot be hidden from other Xyce-only admission scanners.
The preparation owner's absolute deadline covers queue, native work and audit.
"""
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from guarded_native_admission import scan
from run_dco_qualification import ROOT,sha,save


def main():
    out=ROOT/'build/timing400/release_001/hs_diode_geometry_comparison_001'
    plan_path=out/'plan.json'
    plan=json.loads(plan_path.read_text())
    owner_path=out/'owner.json'
    owner=json.loads(owner_path.read_text())
    deadline=owner['absolute_deadline_uptime']
    assert deadline>time.clock_gettime(time.CLOCK_BOOTTIME)
    checker=Path(__file__).with_name('check_hs_diode_comparison.py')
    files=[Path(__file__).resolve(),checker,plan_path,owner_path,
        Path(__file__).with_name('guarded_native_admission.py'),ROOT/'verification/timing450/enforce_native_check_budget.py',
        ROOT/'scripts/sky130_diode_translation_probe.py',ROOT/'scripts/pvt_release_gate.py']
    pins={**plan['input_sha256'],**plan['prepared_deck_sha256'],**{str(p):sha(p) for p in files}}
    assert not (out/'run_owner.json').exists() and not (out/'native_completion.json').exists()
    save(out/'run_owner.json',dict(runner_pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat(),
        original_owner=str(owner_path),absolute_deadline_uptime=deadline,total_budget_restarted=False,
        maximum_native_analog_workers=4,own_native_workers=1,automatic_identical_retry=False))
    save(out/'run_input_manifest.json',dict(input_sha256=pins,scope=__doc__))
    def remaining():
        return deadline-time.clock_gettime(time.CLOCK_BOOTTIME)
    def status(state,**fields):
        save(out/'status.json',dict(state=state,observed_utc=datetime.now(timezone.utc).isoformat(),
            remaining_budget_s=max(0,remaining()),release_qualified=False,**fields))
    def ngspice_processes():
        result=[]
        for p in Path('/proc').glob('[0-9]*'):
            try:
                argv=[s.decode() for s in (p/'cmdline').read_bytes().split(b'\0') if s]
                if argv and argv[0]==plan['ngspice'] and (p/'stat').read_text().rsplit(')',1)[1].split()[0]!='Z':
                    result.append(dict(pid=int(p.name),argv=argv))
            except (FileNotFoundError,ProcessLookupError):
                continue
        return result
    status('checking_prepared_inputs')
    for p,digest in pins.items():
        assert sha(Path(p))==digest,p
    results=[]
    lock_path=ROOT/'build/timing400/guarded_native_admission.lock'
    env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
    for index,job in enumerate(plan['jobs']):
        deck=Path(job['deck'])
        log=Path(job['log'])
        assert sha(deck)==plan['prepared_deck_sha256'][str(deck)] and not log.exists()
        if job['simulator']=='ngspice':
            command=[plan['ngspice'],'-b',str(deck)]
        else:
            command=['apptainer','exec','--bind',f'{ROOT}:{ROOT}','--pwd',str(deck.parent),plan['image'],
                '/opt/xyce/bin/Xyce','-linsolv','KLU','-quiet','-o',job['output_stem'],str(deck)]
        launched=False
        while not launched:
            if remaining()<=0:
                status('timeout_inconclusive_waiting_for_native_capacity',completed=len(results))
                return
            with lock_path.open('a') as lock:
                try:
                    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
                except BlockingIOError:
                    pass
                else:
                    native=scan()
                    reference=ngspice_processes()
                    if len(native)+len(reference)<4:
                        with log.open('x') as output:
                            child=subprocess.Popen(command,stdout=output,stderr=subprocess.STDOUT,
                                cwd=deck.parent,env=env,start_new_session=True)
                            status('native_running',index=index+1,total=360,simulator=job['simulator'],
                                native_pid=child.pid,native_before=native,reference_before=reference,
                                admission_lock_held_through_native_exit=True,job=job)
                            try:
                                code=child.wait(timeout=min(120,max(0,remaining())))
                            except subprocess.TimeoutExpired:
                                os.killpg(child.pid,signal.SIGTERM)
                                try:
                                    child.wait(timeout=10)
                                except subprocess.TimeoutExpired:
                                    os.killpg(child.pid,signal.SIGKILL)
                                    child.wait()
                                status('native_analysis_timeout_inconclusive',index=index+1,job=job,completed=len(results))
                                return
                        assert len(scan())+len(ngspice_processes())<=4
                        results.append(dict(index=index,exit_code=code,command=command,job=job))
                        save(out/'completed_analyses.json',results)
                        if code:
                            status('native_nonpass',index=index+1,job=job,exit_code=code,completed=len(results))
                            return
                        launched=True
            if not launched:
                status('waiting_for_native_capacity',completed=len(results),next_index=index+1)
                time.sleep(min(15,max(0,remaining())))
    status('checking_terminal_provenance',completed=len(results))
    for p,digest in pins.items():
        assert sha(Path(p))==digest,p
    artifacts={str(p):sha(p) for folder in [out/'electrical',out/'noise'] for p in folder.rglob('*')
        if p.is_file() and p.suffix!='.cir'}
    save(out/'native_completion.json',dict(input_sha256=pins,artifacts=artifacts,results=results,
        all_native_analyses_completed=len(results)==360,reference_simulator='ngspice47',
        golden_simulator='upstream Xyce',maximum_native_analog_workers=4,
        original_absolute_deadline_uptime=deadline,geometry_qualified=False,release_qualified=False))
    if remaining()<=0:
        status('timeout_inconclusive_before_assessment')
        return
    with (out/'checker.log').open('x') as log:
        child=subprocess.Popen([sys.executable,str(checker)],stdout=log,stderr=subprocess.STDOUT,cwd=ROOT,start_new_session=True)
        status('assessing_terminal_comparisons',assessment_pid=child.pid)
        try:
            code=child.wait(timeout=remaining())
        except subprocess.TimeoutExpired:
            os.killpg(child.pid,signal.SIGTERM)
            child.wait(timeout=10)
            status('timeout_inconclusive_during_assessment')
            return
    status('terminal_geometry_comparison_passed' if code==0 else 'terminal_comparison_nonpass',checker_exit_code=code)
    print('HS diode comparison assessment exit:',code,'; no PLL model adopted.',flush=True)


if __name__=='__main__':
    main()
