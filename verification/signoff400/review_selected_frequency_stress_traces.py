"""Recompute completed diagnostic matrix acceptance from immutable saved traces."""
import argparse,csv,itertools,json,os,time
from pathlib import Path
from collections import Counter,defaultdict
from common_v3 import save,sha,verify,spec
from resources import lease,identity
from acceptance_v4 import evaluate
from selected_reference_phase import assess as phase_assess


def recompute(case,scenario,phase):
    report=json.loads((case/'assessment.json').read_text())
    if report['native_exit']!=0 or not report['terminal_marker_present']or report['measurement_requests']:raise ValueError('completed covered case required')
    if f'PROGRAMMED400_LOOP_END scenario={scenario}'not in(case/'run.log').read_text():raise ValueError('missing completion marker')
    events={k:[]for k in ['REF','DIV','OUT']};tunes=[]
    with(case/'edges.csv').open()as stream:
        for row in csv.DictReader(stream):events[row['event']].append([float(row['time_ns']),int(row['code']),int(row['bbpd'])])
    with(case/'controls.csv').open()as stream:
        for row in csv.DictReader(stream):
            if row['event']=='ERROR':raise ValueError('model driver error')
            if row['event']=='TUNE':tunes.append([int(row['time_ps'])/1000,int(row['fine'])])
    with(case/'segments.csv').open()as stream:segments=list(csv.DictReader(stream))
    if [int(r['segment'])for r in segments]!=list(range(1 if scenario==0 else 2)):raise ValueError('complete scenario segments required')
    results=[]
    for row in segments:
        start,stop=float(row['enabled_ns']),float(row['stop_ns'])
        if stop-start<220000:raise ValueError('truncated scenario')
        result=evaluate(events,tunes,400,start,stop,spec());stored=json.loads((case/f'segment{row["segment"]}_acceptance.json').read_text())
        if result!=stored:raise ValueError('recomputed segment metrics differ')
        results.append(dict(segment=int(row['segment']),passed=result['passed'],sustained_final_pass=result['sustained_final_pass'],acquisition_confirmed_ns=result['acquisition_confirmed_ns'],enabled_ns=start,final_four_windows=result['windows'][-4:]))
    phase_result=phase_assess(case,scenario,phase)
    if phase_result!=json.loads((case/'reference_phase.json').read_text())or not phase_result['reference_phase_coverage_pass']:raise ValueError('reference-phase evidence differs')
    passed=all(r['passed']for r in results)
    if passed!=report['functional_trace_pass']or report['state']!=('diagnostic_simulation_completed'if passed else'diagnostic_failed'):raise ValueError('recomputed case disposition differs')
    return passed,results


def run(matrix,cpu,output):
    receipt=matrix/'assessment.json';r=json.loads(receipt.read_text());verify(r['input_sha256']);verify(r['artifacts']);rows=json.loads((matrix/'cases.json').read_text());expected=set(itertools.product(['nominal','gain','offset','gain_offset'],['linear_period','linear_frequency'],range(3),[0,10,20,30]))
    if r['completed_cases']!=96 or len(rows)!=96 or {(x['stress'],x['interpolation'],x['scenario'],x['phase_ns'])for x in rows}!=expected or r['needed_native_points']:raise ValueError('complete covered sensitivity matrix required')
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{cpu});save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())));folder=Path(__file__).resolve().parent;pins={str(p):sha(p)for p in [receipt,matrix/'cases.json',Path(__file__).resolve(),folder/'acceptance_v4.py',folder/'selected_reference_phase.py',folder/'common_v3.py']}
    def add(p,d):
        if p in pins and pins[p]!=d:raise ValueError('conflicting shared file identities')
        pins[p]=d
    for row in rows:
        case=Path(row['assessment']).parent;ci=json.loads(Path(row['inputs']).read_text())
        for p,d in ci['input_sha256'].items():add(p,d)
        for p in case.iterdir():
            if p.is_file():add(str(p),sha(p))
    verify(pins);results=[];by=defaultdict(Counter);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+7200
    with lease(1,8,deadline):
        for row in rows:
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('trace review deadline')
            save(output/'status.json',dict(state='recomputing_complete_trace_acceptance',completed_cases=len(results),release_ready=False));passed,segments=recompute(Path(row['assessment']).parent,row['scenario'],row['phase_ns'])
            if passed!=row['functional_trace_pass']:raise ValueError('matrix case disposition differs')
            by[row['stress']]['pass'if passed else'fail']+=1;results.append(dict(stress=row['stress'],interpolation=row['interpolation'],scenario=row['scenario'],phase_ns=row['phase_ns'],passed=passed,segments=segments))
    verify(pins);detail=output/'trace_checks.json';save(detail,results);guard=json.loads((matrix/'image_guard.json').read_text())if(matrix/'image_guard.json').exists()else None
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(detail):sha(detail)},gain_pair=r['gain_pair'],cases_recomputed=96,functional_passes=sum(x['passed']for x in results),by_stress={k:dict(v)for k,v in by.items()},all_saved_segment_metrics_reproduced_exactly=True,all_phase_initializations_recomputed=True,all_trace_files_hashed_before_and_after=True,image_guard=guard,wide_code_stress_applicability_qualified=False,physical_models_qualified=False,release_ready=False));save(output/'status.json',dict(state='complete_trace_acceptance_recomputed',release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--matrix',type=Path,required=True);p.add_argument('--cpu',type=int,choices=[25,26],required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.matrix.resolve(),a.cpu,a.output.resolve())
