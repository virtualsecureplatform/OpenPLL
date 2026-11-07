"""Search diagnostic TT gains with actual selected RTL and both publication views.

Reuse the initial queued pair. Missing tuning coverage stays indeterminate while other gains are explored.
Incomplete execution stops expansion. A TT result never qualifies a common five-corner gain.
"""
import argparse,json,os,subprocess,time
from pathlib import Path
from common_v3 import ROOT,PROFILE,save,sha,verify,spec
from selected_physical_rtl import source_pins
from resources import identity


def grid(profile):
    pairs=sorted({(ki,kp)for ki in profile['gain_search']['ki']for kp in profile['gain_search']['kp']})
    first=tuple(profile['gain_search']['first'])
    if first not in pairs:raise ValueError('initial gain must belong to declared grid')
    return first,pairs


def disposition(reports):
    if not reports:raise ValueError('nonempty actual case reports required')
    if any(r['state']=='needs_native_tuning_points'for r in reports):return 'missing_native_coverage'
    if any(r.get('native_exit')!=0 or r.get('terminal_marker_present')is not True for r in reports):return 'incomplete_execution'
    if any(r['state']not in('diagnostic_failed','diagnostic_simulation_completed')for r in reports):raise ValueError('unsupported terminal case state')
    return 'pass'if all(r.get('functional_trace_pass')is True and r.get('reference_phase_coverage_pass')is True and r['state']=='diagnostic_simulation_completed'for r in reports)else 'functional_failure'



def selection_audit(records,selected):
    """A candidate pass cannot resolve unassessed or unknown lower-ranked pairs."""
    first,pairs=grid(spec())
    if selected is None:return dict(selection_order_resolved=False,unresolved_lower_gain_pairs=[])
    selected=tuple(selected)
    if selected not in pairs:raise ValueError('declared selected pair required')
    evidence={(r['ki'],r['kp']):r['disposition'] for r in records}
    if evidence.get(selected)!='pass':raise ValueError('complete passing candidate required')
    lower=[p for p in pairs if p<selected]
    unknown=[list(p)for p in lower if evidence.get(p) not in ['pass','functional_failure']]
    if any(evidence.get(p)=='pass' for p in lower):raise ValueError('a lower pair already passed')
    return dict(selection_order_resolved=not unknown,unresolved_lower_gain_pairs=unknown)


def run(pipeline,nominal,stress,output):
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{26});save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    records=[];children=[]
    try:
        profile=spec();first,pairs=grid(profile);folder=Path(__file__).resolve().parent
        bases=[nominal,stress];compositions=[ROOT/'build/signoff400/selected_root_publication_detector_407',ROOT/'build/signoff400/selected_receiver_stress_detector_450'];caches=[ROOT/'build/signoff400/selected_nominal_RTL_build_cache_778',ROOT/'build/signoff400/selected_stress_RTL_build_cache_788']
        image=ROOT/'build/apptainer/openpll-release-modern.sif';worker=folder/'follow_selected_publication_matrix_v3.py'
        paths=[Path(__file__).resolve(),worker,PROFILE,image,folder/'selected_physical_rtl.py',folder/'common_v3.py',folder/'resources.py',pipeline/'owner.json',*(b/'owner.json'for b in bases),*(b/'inputs.json'for b in bases),*(c/'assessment.json'for c in compositions),*(c/'assessment.json'for c in caches)]
        pins=source_pins();pins.update({str(p):sha(p)for p in paths});verify(pins)
        save(output/'inputs.json',dict(input_sha256=pins,reused_initial_matrices=list(map(str,bases)),first_gain=list(first),search_wall_cap_s=43200,ordered_gain_grid=[list(p)for p in pairs],operating_point='TT nominal only',maximum_additional_matrices=2*(len(pairs)-1),native_launches_allowed=0,release_ready=False))
        deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+432000
        for base in bases:
            owner=json.loads((base/'owner.json').read_text())
            while True:
                state=json.loads((base/'status.json').read_text())['state']
                if state=='scenario_phase_matrix_assessed':break
                if state=='stopped_without_qualification'or identity(owner['pid'])!=owner['birth']:raise RuntimeError('original baseline matrix stopped without assessment')
                if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('baseline observation deadline; original jobs unchanged')
                save(output/'status.json',dict(state='waiting_for_initial_gain_matrices',matrix=str(base),release_ready=False));time.sleep(10)
        search_deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
        os.environ.update(OMP_NUM_THREADS='1',OMP_THREAD_LIMIT='1',OPENBLAS_NUM_THREADS='1')
        def evaluate(pair):
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=search_deadline:raise TimeoutError('whole diagnostic gain search deadline')
            existing=next((r for r in records if (r['ki'],r['kp'])==pair),None)
            if existing:return existing
            directories=bases if pair==first else [output/f'ki{pair[0]}_kp{pair[1]}_{name}'for name in('nominal','stress')]
            if pair!=first:
                for directory,composition,cache in zip(directories,compositions,caches):
                    command=list(map(str,['/usr/bin/python3',worker,'--pipeline',pipeline,'--composition',composition,'--build-cache',cache,'--ki',pair[0],'--kp',pair[1],'--cpu',26,'--output',directory]))
                    with(output/(directory.name+'.log')).open('x')as log:child=subprocess.Popen(command,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
                    children.append(dict(pid=child.pid,birth=identity(child.pid),command=command));save(output/'children.json',dict(records=children,release_ready=False));bound=min(time.clock_gettime(time.CLOCK_BOOTTIME)+7200,search_deadline)
                    while child.poll()is None:
                        if time.clock_gettime(time.CLOCK_BOOTTIME)>=bound:raise TimeoutError('matrix observer deadline; independently bounded child unchanged')
                        save(output/'status.json',dict(state='gain_matrix_running',gain=list(pair),matrix=str(directory),release_ready=False));time.sleep(10)
                    if child.returncode:raise RuntimeError('matrix stage stopped; no identical retry')
            reports=[];requests=[]
            for directory,composition,cache in zip(directories,compositions,caches):
                p=directory/'assessment.json';a=json.loads(p.read_text());verify(a['input_sha256']);verify(a['artifacts']);pins[str(p)]=sha(p)
                if a['input_sha256'].get(str(pipeline/'owner.json'))!=sha(pipeline/'owner.json'):raise ValueError('matrix follows another calibration pipeline')
                if (a['ki'],a['kp'])!=pair or a['expected_cases']!=24 or a['compiled_build_reused']is not True:raise ValueError('complete cached matrix at requested gain required')
                if a['input_sha256'].get(str(composition/'assessment.json'))!=sha(composition/'assessment.json')or a['input_sha256'].get(str(cache/'assessment.json'))!=sha(cache/'assessment.json'):raise ValueError('publication view/cache identity differs')
                expected={(k,i,p)for k in('linear_period','linear_frequency')for i in range(3)for p in profile['reference_phase_offsets_ns']}
                if len(a['records'])!=24 or {(r['interpolation'],r['scenario'],r['phase_ns'])for r in a['records']}!=expected:raise ValueError('complete scenario/phase/interpolation matrix required')
                for row in a['records']:
                    path=Path(row['assessment'])
                    if sha(path)!=row['assessment_sha256']:raise ValueError('case assessment changed')
                    report=json.loads(path.read_text());case_inputs=Path(row['inputs']);ci=json.loads(case_inputs.read_text());verify(ci['input_sha256'])
                    if sha(case_inputs)!=row['inputs_sha256']:raise ValueError('case input receipt changed')
                    for artifact in path.parent.iterdir():
                        if artifact.is_file():pins[str(artifact)]=sha(artifact)
                    reports.append(report)
                requests+=a['requested_native_points']
            record=dict(ki=pair[0],kp=pair[1],disposition=disposition(reports),matrices=list(map(str,directories)),cases=len(reports),measurement_requests=requests)
            records.append(record);save(output/'trials.json',records);return record
        selected=None;reason=None;initial=evaluate(first)
        if initial['disposition']=='incomplete_execution':reason=initial['disposition']
        else:
            for pair in pairs:
                record=evaluate(pair)
                if record['disposition']=='pass':selected=pair;break
                if record['disposition']=='incomplete_execution':reason=record['disposition'];break
            if selected is None and reason is None:
                reason='unresolved_native_coverage' if any(r['disposition']=='missing_native_coverage' for r in records) else 'no_functional_pair_in_declared_grid'
        selection=selection_audit(records,selected)
        verify(pins)
        save(output/'assessment.json',dict(input_sha256=pins,trials=records,selected_TT_diagnostic_gain=list(selected)if selected else None,stop_reason=reason,
            evaluated_first_then_lowest_KI_KP=True,selection_order_resolved=selection["selection_order_resolved"],unresolved_lower_gain_pairs=selection["unresolved_lower_gain_pairs"],both_publication_views_checked=True,native_launches=0,common_five_corner_gain_qualified=False,uniform_model_uncertainty_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='TT_gain_diagnostic_assessed',stop_reason=reason,release_ready=False))
    except BaseException as e:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(e),original_jobs_unchanged=True,release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in('pipeline','nominal','stress','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve()for n in('pipeline','nominal','stress','output')))
