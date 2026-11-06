"""Compare complete original/folded checkpoint traces and measured runtimes.

Requires the same initialization, condition, native executable and original
horizon, with the reduced input pinned to its certified affine transform.
This reports one sampled voltage response, not power or whole-family bounds.
"""
import argparse,json,os,time
from pathlib import Path
from common_v3 import save,sha,verify
from resources import identity
from assess_selected_detector_prefix import read_prefix
from compare_selected_dco_startup_aligned_v5 import aligned,metrics


def elapsed(directory):
    # Native process birth uses kernel clock ticks; /proc does not retain exit time.
    # Use the backend's own elapsed-time report rather than observer wall time.
    import re
    text=(directory/'native.log').read_text()
    found=re.findall(r'Total Simulation Solvers Run Time:\s*([0-9.eE+-]+)',text)
    return float(found[-1]) if len(found)==1 else None


def run(original,folded,output,wait=False):
    os.sched_setaffinity(0,{30});output.mkdir(parents=True,exist_ok=False)
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    owners=[json.loads((p/'owner.json').read_text())for p in (original,folded)]
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+12600
    try:
        while True:
            states=[json.loads((p/'status.json').read_text())for p in (original,folded)]
            if any(s['state']=='stopped_without_qualification'for s in states):raise ValueError('original or folded case terminal without normal completion')
            if all(s['state']=='saved_state_DCO_diagnostic_complete'for s in states):break
            if not wait:raise ValueError('both normal native completions required')
            for directory,state,owner in zip((original,folded),states,owners):
                if state['state']=='saved_state_DCO_diagnostic_complete':continue
                if identity(owner['pid'])!=owner['birth']:raise RuntimeError('original native controller disappeared without terminal result')
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('comparison observation deadline; original native jobs unchanged')
            save(output/'status.json',dict(state='waiting_for_original_and_folded_normal_native_results',release_ready=False));time.sleep(10)
        manifests=[];traces=[];pins={}
        for directory in (original,folded):
            manifest=directory/'manifest.json';m=json.loads(manifest.read_text());verify(m['input_sha256'])
            worker=json.loads((directory/'native.process.json').read_text())
            if identity(worker['pid'])==worker['birth']:raise ValueError('terminal native worker required')
            raw=directory/'control.raw';assessment=directory/'assessment.json';a=json.loads(assessment.read_text())
            verify(a['input_sha256']);verify(a['artifacts'])
            if a['artifacts'].get(str(raw))!=sha(raw):raise ValueError('complete native waveform not pinned')
            rows,info=read_prefix(raw,m['observed_roles'])
            if info['incomplete_final_sample_discarded'] or abs(rows[-1][0]-m['simulation_end_s'])>1e-18:raise ValueError('same complete original horizon required')
            edges,startup=aligned(rows,1,2)
            if startup['end_age_ns']<40:raise ValueError('full common 10--40 ns oscillator-age coverage required')
            traces.append((edges,startup));manifests.append(m)
            for path in (manifest,raw,assessment,directory/'status.json',directory/'native.process.json',directory/'native.log'):pins[str(path)]=sha(path)
        a,b=manifests
        for key in ('controls','operating_point','observed_roles','native_checkpoint_time_s','simulation_end_s','initialized_private_nodes','DCOP_skipped'):
            if a[key]!=b[key]:raise ValueError('initialization or condition differs: '+key)
        binaries=[{p:d for p,d in m['input_sha256'].items()if p.endswith('/Xyce')}for m in manifests]
        if len(binaries[0])!=1 or binaries[0]!=binaries[1]:raise ValueError('same actual native executable required')
        if b['original_native_case']!=str(original) or b['original_native_case_manifest_sha256']!=sha(original/'manifest.json'):
            raise ValueError('folded native case not bound to original')
        transform=[Path(p)for p in b['input_sha256']if p.endswith('/assessment.json')and 'fixed_boundary_fold' in p]
        if len(transform)!=1:raise ValueError('one certified affine transform required')
        certificate=json.loads(transform[0].read_text());verify(certificate['input_sha256']);verify(certificate['artifacts'])
        if not certificate['serialized_free_C_passivity_certified'] or not certificate['retained_node_equations_exact_before_serialization']:
            raise ValueError('source and serialized operator certificates required')
        pins[str(transform[0])]=sha(transform[0])
        result=metrics(traces[1][0],traces[0][0],40)
        for row in result.values():row['folded']=row.pop('candidate');row['original']=row.pop('full_native')
        start_shift=1000*(traces[1][1]['first_oscillator_rise_ns']-traces[0][1]['first_oscillator_rise_ns'])
        native_times=[elapsed(p)for p in (original,folded)]
        paths=[Path(__file__).resolve()]+[Path(__file__).with_name(n)for n in ('common_v3.py','resources.py','assess_selected_detector_prefix.py','compare_selected_dco_startup_aligned_v5.py','assess_selected_detector_phase_probe_v2.py')]
        pins.update({str(p):sha(p)for p in paths});verify(pins)
        save(output/'assessment.json',dict(input_sha256=pins,normal_full_windows_completed=True,frequency_comparisons=result,
            first_oscillator_rise_difference_ps=start_shift,original_native_solver_elapsed_s=native_times[0],folded_native_solver_elapsed_s=native_times[1],
            solver_time_ratio_original_to_folded=native_times[0]/native_times[1]if all(t is not None and t>0 for t in native_times)else None,
            timing_scope='native reported solver time only; different simultaneous host workloads are not a controlled throughput benchmark',
            fixed_source_current_or_power_qualified=False,whole_family_response_equivalence_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='original_folded_native_response_assessed',release_ready=False));print(json.dumps(result))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('original','folded','output'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--wait',action='store_true');a=p.parse_args()
    run(*(getattr(a,n).resolve()for n in ('original','folded','output')),a.wait)
