"""Compare normally completed held-versus-replayed reference boundary controls."""
import argparse,json,os,time
from pathlib import Path
from common_v3 import save,sha,verify
from resources import identity,lease
from assess_selected_detector_prefix import read_prefix
from compare_selected_dco_startup_aligned_v2 import aligned,window_frequency
from audit_selected_dco_history_inputs import sources
from compare_selected_dco_load_controls import canonical_deck


def run(baseline,target,output):
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{28})
    folders=[baseline,target];owners=[json.loads((p/'owner.json').read_text()) for p in folders]
    files=[Path(__file__).resolve(),Path(__file__).with_name('assess_selected_detector_prefix.py'),Path(__file__).with_name('compare_selected_dco_startup_aligned_v2.py'),Path(__file__).with_name('compare_selected_dco_load_controls.py'),Path(__file__).with_name('audit_selected_dco_history_inputs.py')]
    pins={str(p):sha(p) for p in files}
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    save(output/'inputs.json',dict(input_sha256=pins,original_owners=owners,baseline=str(baseline),target=str(target),automatic_native_launch=False,release_ready=False))
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+12600
    try:
        while True:
            pending=[]
            for p,owner,terminal in zip(folders,owners,['real_driver_DCO_diagnostic_complete','reference_forcing_control_completed']):
                state=json.loads((p/'status.json').read_text())['state']
                if state==terminal:continue
                if state=='stopped_without_qualification' or identity(owner['pid'])!=owner['birth']:raise RuntimeError('original control stopped before normal completion: '+str(p))
                pending.append(str(p))
            if not pending:break
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('observation deadline; original native controls unchanged')
            save(output/'status.json',dict(state='waiting_for_original_reference_forcing_controls',pending=pending,release_ready=False));time.sleep(10)
        with lease(1,2,deadline):
            bm,tm=[json.loads((p/'manifest.json').read_text()) for p in folders]
            for m in [bm,tm]:verify(m['input_sha256'])
            if any(bm[k]!=tm[k] for k in ['operating_point','controls','observed_roles']):raise ValueError('matched physical programming/observation required')
            if sha(baseline/'devices.spice')!=sha(target/'devices.spice') or canonical_deck((baseline/'control.spice').read_text())!=canonical_deck((target/'control.spice').read_text()):raise ValueError('physical circuit, solver or horizon changed')
            a,b=[sources(p/'sources.spice') for p in folders]
            if a.keys()!=b.keys() or any(a[n][0]!=b[n][0] for n in a):raise ValueError('source inventory changed')
            changed={n for n in a if a[n][1]!=b[n][1]}
            if changed!=set(tm['changed_voltage_sources']) or len(changed)!=2:raise ValueError('exactly two reference source values must change')
            waves=[]
            for p,m in zip(folders,[bm,tm]):
                worker=json.loads((p/'native.process.json').read_text())
                if identity(worker['pid'])==worker['birth']:raise ValueError('native worker still live')
                rows,info=read_prefix(p/'control.raw',m['observed_roles'])
                if info['declared_samples']!=len(rows) or info['incomplete_final_sample_discarded'] or abs(rows[-1][0]-60e-9)>1e-18:raise ValueError('complete finite 60 ns observations required')
                edges,startup=aligned(rows,1,2);waves.append((edges,startup))
            comparisons={}
            for name,start,stop in [('common',10,40),('early',10,25),('late',25,40)]:
                x,y=[window_frequency(w[0],start,stop) for w in waves]
                comparisons[name]=dict(window_after_first_rise_ns=[start,stop],held_reference=x,replayed_reference=y,difference_ppm=1e6*(y['frequency_mhz']/x['frequency_mhz']-1))
            phases=[(y-x)*1000 for x,y in zip(waves[0][0],waves[1][0]) if 10<=min(x,y) and max(x,y)<=40]
            if len(phases)<3:raise ValueError('at least three paired oscillator edges required')
            for p in folders:
                for name in ['manifest.json','assessment.json','control.raw','devices.spice','sources.spice','control.spice']:pins[str(p/name)]=sha(p/name)
            verify(pins)
            save(output/'assessment.json',dict(input_sha256=pins,comparisons=comparisons,
                phase_trajectory_difference_after_first_rise_alignment_ps=dict(minimum=min(phases),maximum=max(phases),paired_edges=len(phases)),
                changed_reference_boundary_nodes=sorted(changed),source_window=tm['recorded_reference_sources'],
                initial_reference_phase_and_voltage_histories_differ=True,conditional_forcing_control_only=True,
                numerical_convergence_qualified=False,uniform_frequency_or_phase_uncertainty_bound_qualified=False,physical_models_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='reference_forcing_controls_compared',release_ready=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['baseline','target','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve() for n in ['baseline','target','output']))
