"""Compare the two measured code increments; never fit away correlation error."""
import argparse,json,os,time
from pathlib import Path
from common_v3 import save,sha,verify
from resources import identity,lease
from audit_selected_dco_history_inputs import sources
from compare_selected_dco_load_controls import canonical_deck


def run(base,target,first,followup,inventory,output):
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{29})
    owner=json.loads((followup/'owner.json').read_text());files=[Path(__file__).resolve(),first,followup/'owner.json',inventory,Path(__file__).with_name('audit_selected_dco_history_inputs.py'),Path(__file__).with_name('compare_selected_dco_load_controls.py')];pins={str(p):sha(p) for p in files}
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())));save(output/'inputs.json',dict(input_sha256=pins,original_followup=str(followup),original_owner=owner,automatic_native_launch=False,release_ready=False));deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+14400
    try:
        while not (followup/'assessment.json').exists():
            state=json.loads((followup/'status.json').read_text())['state']
            if state=='stopped_without_qualification' or identity(owner['pid'])!=owner['birth']:raise RuntimeError('original code holdout collector stopped')
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('observation deadline; native untouched')
            save(output/'status.json',dict(state='waiting_for_original_fine112_comparison',release_ready=False));time.sleep(10)
        with lease(1,1,deadline):
            a=json.loads(first.read_text());b=json.loads((followup/'comparison/assessment.json').read_text());bm,tm=[json.loads((d/'manifest.json').read_text()) for d in [base,target]]
            for x in [a,b,bm,tm]:verify(x['input_sha256'])
            if (a['coarse'],a['fine'],b['coarse'],b['fine'])!=(20,111,20,112):raise ValueError('matching native 111/112 code pair required')
            if (base/'devices.spice').read_bytes()!=(target/'devices.spice').read_bytes() or bm['observed_roles']!=tm['observed_roles']:raise ValueError('identical retained physical circuit and observations required')
            if canonical_deck((base/'control.spice').read_text())!=canonical_deck((target/'control.spice').read_text()):raise ValueError('same solver settings required')
            iv=json.loads(inventory.read_text());verify(iv['input_sha256']);node=iv['controls']['DCO_THERM[111]']['driver_input_node'];x,y=sources(base/'sources.spice'),sources(target/'sources.spice')
            if set(x)!=set(y) or {n for n in x if x[n][1]!=y[n][1]}!={node}:raise ValueError('only the expected programming input may change')
            records=[]
            for window in ['common','early','late']:
                u,v=a['frequency_comparisons'][window],b['frequency_comparisons'][window]
                if u['window_after_first_rise_ns']!=v['window_after_first_rise_ns']:raise ValueError('same oscillator-age windows required')
                reduced=v['candidate']['frequency_mhz']-u['candidate']['frequency_mhz'];full=v['full_native']['frequency_mhz']-u['full_native']['frequency_mhz']
                if reduced<=0 or full<=0:raise ValueError('unexpected non-increasing measured tuning increment')
                records.append(dict(window=window,oscillator_age_ns=u['window_after_first_rise_ns'],reduced_increment_mhz=reduced,full_increment_mhz=full,increment_ratio=reduced/full,increment_error_percent=100*(reduced/full-1),fine111_frequency_error_ppm=u['difference_ppm'],fine112_frequency_error_ppm=v['difference_ppm']))
            files += [followup/'assessment.json',followup/'comparison/assessment.json']+[d/n for d in [base,target] for n in ['manifest.json','devices.spice','sources.spice','control.spice']];pins.update({str(p):sha(p) for p in files});verify(pins)
            save(output/'assessment.json',dict(input_sha256=pins,records=records,same_reduced_physical_circuit=True,only_expected_fine_driver_input_changed=True,constant_offset_correction_applied=False,scope='two-code sampled reduced/full tuning increment under oscillator-age alignment; exterior and reset histories remain conditional',tuning_curve_qualified=False,uniform_uncertainty_bound_qualified=False,release_ready=False));print(json.dumps(records))
        save(output/'status.json',dict(state='native_two_code_increment_compared',release_ready=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['base','target','first','followup','inventory','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve() for n in ['base','target','first','followup','inventory','output']))
