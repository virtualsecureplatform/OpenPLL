"""Wait for both normal static DCO captures, then measure load and window sensitivity."""
import os
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
import json
from pathlib import Path
import re
import time
from common_v3 import ROOT,save,sha,verify
from resources import identity,lease
from assess_selected_detector_phase_probe_v2 import read_selected
from assess_selected_isolated_control import frequency


def normalized_deck(text):
    return re.sub(r'file=\S+','file=OUTPUT','\n'.join(line for line in text.splitlines()
        if not line.startswith('*') and not line.startswith('C_RECEIVER ')))


def run():
    base=ROOT/'build/signoff400'
    cases=[base/'selected_keeper_static_terminated_DCO_1531',base/'selected_keeper_static_zero_load_DCO_1536']
    output=base/'selected_keeper_static_load_pair_1538'
    output.mkdir(exist_ok=False)
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    os.sched_setaffinity(0,{31})
    deadline=time.monotonic()+86400
    try:
        while True:
            pending=[]
            for case in cases:
                state=json.loads((case/'status.json').read_text())['state']
                if state=='static_terminated_DCO_capture_complete':continue
                if state=='stopped_without_qualification':raise RuntimeError('capture stopped: '+str(case))
                owner=json.loads((case/'owner.json').read_text())
                if identity(owner['pid'])!=owner['birth']:raise RuntimeError('missing capture owner: '+str(case))
                pending.append(str(case))
            if not pending:break
            if time.monotonic()>=deadline:raise TimeoutError('pair observation cap')
            save(output/'status.json',dict(state='waiting_for_normal_completed_captures',pending=pending,release_ready=False))
            time.sleep(10)
        save(output/'status.json',dict(state='assessing_completed_captures',release_ready=False))
        decks=[(case/'transient.spice').read_text() for case in cases]
        if normalized_deck(decks[0])!=normalized_deck(decks[1]):raise ValueError('unexpected paired electrical difference')
        if 'C_RECEIVER RECEIVER 0 32f' not in decks[0] or 'C_RECEIVER ' in decks[1]:raise ValueError('declared load pair required')
        files=[Path(__file__).resolve(),Path(__file__).with_name('assess_selected_detector_phase_probe_v2.py'),
               Path(__file__).with_name('assess_selected_isolated_control.py')]
        diagnostics=[]
        with lease(1,8,time.clock_gettime(time.CLOCK_BOOTTIME)+3600):
            for case in cases:
                receipt=case/'assessment.json';record=json.loads(receipt.read_text())
                verify(record['input_sha256']);verify(record['artifacts'])
                if not all(record[k] for k in ['normal_native_completion','all_saved_values_finite','all_native_DCO_leaves_match']):
                    raise ValueError('normal finite capture with all native leaf checks required')
                files.extend([receipt,case/'transient.spice'])
                rows=read_selected(case/'transient.raw',{'PLLOUT':'PLLOUT'},60e-9)
                windows=[]
                for low,high in [(20,40),(40,60),(20,60)]:
                    reason=None
                    try:f=frequency(rows,low,high)
                    except ValueError as error:f=None;reason=str(error)
                    windows.append(dict(window_ns=[low,high],frequency=f,unavailable_reason=reason))
                diagnostics.append(dict(case=str(case),windows=windows,native_elapsed_s=record['native_elapsed_s']))
        full=[d['windows'][-1]['frequency'] for d in diagnostics]
        difference=(full[0]['frequency_mhz']/full[1]['frequency_mhz']-1)*1e6 if all(full) else None
        save(output/'assessment.json',dict(input_sha256={str(p):sha(p) for p in files},artifacts={},
             cases=diagnostics,load32_relative_to_zero_ppm=difference,
             electrical_decks_match_except_declared_load=True,
             full_startup_histories_correlated=False,receiver_load_qualified=False,
             startup_window_qualified=False,independent_model_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='completed_static_load_pair_assessed',release_ready=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise


if __name__=='__main__':run()
