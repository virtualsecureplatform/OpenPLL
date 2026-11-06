"""Measure a short reset-sparsity response without relaxing the full-window criterion."""
import argparse,json,os,time
from pathlib import Path
from common_v3 import save,sha,verify
from resources import identity
from assess_selected_detector_prefix import read_prefix
from compare_selected_dco_startup_aligned_v5 import aligned,window_frequency

def run(baseline,candidate,audit,output,wait=False):
    os.sched_setaffinity(0,{30});output.mkdir(parents=True,exist_ok=False)
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+12600
    try:
        audit_record=json.loads(audit.read_text());verify(audit_record['input_sha256'])
        for key in ('physical_network_private_voltages_and_solver_identical','all_other_boundary_sources_identical','only_reset_PWL_changed','reset_endpoints_and_10_50_90_percent_crossing_times_preserved'):
            if audit_record.get(key)is not True:raise ValueError('independent reset-only input audit required')
        for d in (baseline,candidate):
            p=d/'manifest.json'
            if audit_record['input_sha256'].get(str(p))!=sha(p):raise ValueError('audited baseline/candidate identity mismatch')
        while True:
            statuses=[json.loads((d/'status.json').read_text())for d in (baseline,candidate)]
            live=[s['state']in ('preparing_saved_state_DCO_diagnostic','saved_state_DCO_native_running')for s in statuses]
            if not any(live):break
            if not wait:raise ValueError('terminal native prefixes required')
            for d,pending in zip((baseline,candidate),live):
                if pending:
                    owner=json.loads((d/'owner.json').read_text())
                    if identity(owner['pid'])!=owner['birth']:raise RuntimeError('original native controller disappeared')
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('observer deadline; native unchanged')
            save(output/'status.json',dict(state='waiting_for_original_reset_controls',release_ready=False));time.sleep(10)
        pins={str(audit):sha(audit)};measurements=[]
        for d,status in zip((baseline,candidate),statuses):
            complete=status['state']=='saved_state_DCO_diagnostic_complete'
            budget=status['state']=='stopped_without_qualification'and 'TimeoutError'in status.get('reason','')
            if not(complete or budget):raise ValueError('normal completion or explicit native budget stop required')
            worker=json.loads((d/'native.process.json').read_text())
            if identity(worker['pid'])==worker['birth']:raise ValueError('original native worker still live')
            m=json.loads((d/'manifest.json').read_text());verify(m['input_sha256'])
            raw=d/'control.raw';rows,info=read_prefix(raw,m['observed_roles']);edges,startup=aligned(rows,1,2)
            if startup['end_age_ns']<20:raise ValueError('complete explicitly short 10--20 ns window required')
            if complete and abs(rows[-1][0]-m['simulation_end_s'])>1e-18:raise ValueError('normal result is missing original endpoint')
            measurements.append(dict(frequency=window_frequency(edges,10,20),startup=startup,
                normal_full_horizon_completed=complete,native_budget_stopped=budget,prefix_info=info))
            for name in ('manifest.json','status.json','native.process.json','control.raw'):pins[str(d/name)]=sha(d/name)
        a,b=measurements
        paths=[Path(__file__).resolve()]+[Path(__file__).with_name(n)for n in ('common_v3.py','resources.py','assess_selected_detector_prefix.py','compare_selected_dco_startup_aligned_v5.py','assess_selected_detector_phase_probe_v2.py')]
        pins.update({str(p):sha(p)for p in paths});verify(pins)
        save(output/'assessment.json',dict(input_sha256=pins,baseline=a,candidate=b,
            measured_oscillator_age_window_ns=[10,20],required_full_common_age_window_ns=[10,40],
            full_common_window_criterion_satisfied=False,
            candidate_vs_tight_reset_frequency_difference_ppm=1e6*(b['frequency']['frequency_mhz']/a['frequency']['frequency_mhz']-1),
            first_output_rise_difference_ps=1000*(b['startup']['first_oscillator_rise_ns']-a['startup']['first_oscillator_rise_ns']),
            scope='Short-window diagnostic of the independently audited reset-only perturbation. This does not replace the required full 10--40 ns comparison, establish a charge/response bound or qualify reset sparsity.',
            uniform_reset_response_bound_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='short_reset_response_assessed_full_criterion_unmet',release_ready=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('baseline','candidate','audit','output'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--wait',action='store_true');a=p.parse_args()
    run(*(getattr(a,n).resolve()for n in ('baseline','candidate','audit','output')),a.wait)
