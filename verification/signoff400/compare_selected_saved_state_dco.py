"""Compare a terminal saved-state DCO control to full native and history replay."""
import argparse,csv,json,os,time
from pathlib import Path
from common_v3 import save,sha,verify
from resources import identity
from assess_selected_detector_prefix import read_prefix
from compare_selected_dco_startup_aligned_v5 import aligned,metrics
from selected_spice_device_conditions import matching,reference_deck


def run(native,reference_provenance,history,output,wait=False):
    os.sched_setaffinity(0,{30});output.mkdir(parents=True,exist_ok=False)
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    owner=json.loads((native/'owner.json').read_text());deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+12600
    try:
        while True:
            status=json.loads((native/'status.json').read_text())
            if status['state'] not in ('preparing_saved_state_DCO_diagnostic','saved_state_DCO_native_running'):break
            if not wait:raise ValueError('saved-state native diagnostic remains live')
            if identity(owner['pid'])!=owner['birth']:raise RuntimeError('original controller exited without terminal status')
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('observation deadline; original native unchanged')
            save(output/'status.json',dict(state='waiting_for_original_saved_state_native',release_ready=False));time.sleep(10)
        complete=status['state']=='saved_state_DCO_diagnostic_complete'
        budget=status['state']=='stopped_without_qualification' and 'TimeoutError' in status.get('reason','')
        if not (complete or budget):raise ValueError('normal completion or explicit original budget stop required')
        worker=json.loads((native/'native.process.json').read_text())
        if identity(worker['pid'])==worker['birth']:raise ValueError('original native remains live')
        m=json.loads((native/'manifest.json').read_text());verify(m['input_sha256'])
        if (m['controls']['coarse'],m['controls']['fine'])!=(20,111):raise ValueError('same TT20/111 diagnostic required')
        provenance=json.loads(reference_provenance.read_text());verify(provenance['input_sha256']);verify(provenance['artifacts'])
        reference=reference_provenance.parent/'signals.csv';assessment=reference_provenance.parent/'assessment.json'
        for path in (reference,assessment):
            if provenance['artifacts'].get(str(path))!=sha(path):raise ValueError('full reference artifact not bound to native')
        a=json.loads(assessment.read_text())
        if a['end_ns']!=260 or a['coarse_code']['window_codes']!=[20] or a['dco_code']['window_codes']!=[111]:raise ValueError('same complete native code required')
        baseline_paths=[Path(x)for x in m['input_sha256']if x.endswith('/manifest.json')]
        if len(baseline_paths)!=1:raise ValueError('unique history baseline manifest required')
        baseline=json.loads(baseline_paths[0].read_text());verify(baseline['input_sha256'])
        model={x:h for x,h in baseline['input_sha256'].items()if x.endswith('/model.spice')}
        if len(model)!=1 or any(provenance['native_input_sha256'].get(x)!=h for x,h in model.items()):raise ValueError('same physical model required')
        physical=reference_deck(provenance);conditions=matching(native/'control.spice',physical)
        if conditions['corner']!='tt':raise ValueError('same TT native conditions required')
        with reference.open()as stream:
            reader=csv.reader(stream);names=next(reader);full=[[float(v)for v in row]for row in reader]
        if len(full)!=a['samples']:raise ValueError('assessed native sample count differs')
        raw=native/'control.raw';rows,info=read_prefix(raw,m['observed_roles'])
        if complete and (info['incomplete_final_sample_discarded'] or abs(rows[-1][0]-m['simulation_end_s'])>1e-18):raise ValueError('complete saved-state time span required')
        candidate,cm=aligned(rows,1,2);ref,rm=aligned(full,names.index('v(pllout)'),names.index('v(xpll:__parent_r_node_617)'))
        if min(cm['end_age_ns'],rm['end_age_ns'])<40:raise ValueError('complete 10--40 ns oscillator-age coverage required')
        result=metrics(candidate,ref,40)
        h=json.loads(history.read_text());verify(h['input_sha256'])
        if (h['coarse'],h['fine'])!=(20,111):raise ValueError('same recorded-history control required')
        direct={}
        for label,row in result.items():
            prior=h['frequency_comparisons'][label]
            if prior['window_after_first_rise_ns']!=row['window_after_first_rise_ns'] or prior['full_native']!=row['full_native']:raise ValueError('same native reference and age windows required')
            direct[label]=dict(saved_state_vs_recorded_history_ppm=1e6*(row['candidate']['frequency_mhz']/prior['candidate']['frequency_mhz']-1))
        paths=[reference_provenance,reference,assessment,history,baseline_paths[0],physical,raw,native/'manifest.json',native/'status.json',native/'native.process.json',Path(__file__).resolve()]
        paths += [Path(__file__).with_name(n)for n in ('common_v3.py','resources.py','assess_selected_detector_prefix.py','compare_selected_dco_startup_aligned_v5.py','assess_selected_detector_phase_probe_v2.py','selected_spice_device_conditions.py')]
        pins={str(p):sha(p)for p in paths};verify(pins)
        save(output/'assessment.json',dict(input_sha256=pins,normal_full_window_completed=complete,native_budget_stopped=budget,
             checkpoint_time_s=m['native_checkpoint_time_s'],initialized_private_nodes=m['initialized_private_nodes'],
             candidate_startup=cm,full_native_startup=rm,frequency_comparisons=result,history_comparisons=direct,
             nonlinear_restart_qualified=False,uniform_uncertainty_bound_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='saved_state_native_comparison_assessed',release_ready=False));print(json.dumps(result))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('native','reference-provenance','history','output'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--wait',action='store_true');a=p.parse_args()
    run(*(getattr(a,n.replace('-','_')).resolve()for n in ('native','reference-provenance','history','output')),a.wait)
