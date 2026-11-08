"""Collect a completed, physically checked TT curve and independently characterize a holdout."""
import argparse,json,math,os,time
for _thread_variable in ("OPENBLAS_NUM_THREADS","OMP_NUM_THREADS","MKL_NUM_THREADS"):
    os.environ[_thread_variable]="1"
from pathlib import Path
from common_v3 import save,sha,verify
from resources import identity,lease
from extract_keeper_replay_waveforms import completed_reference

def characterize(points,holdout,target_hz=400e6):
    points=sorted(points,key=lambda r:r['fine']);codes=[r['fine'] for r in points]
    if len(points)<2 or len(set(codes))!=len(codes) or holdout['fine'] in codes:raise ValueError('unique fit points and independent holdout required')
    if any(type(r['frequency_hz']) not in (float,int) or not math.isfinite(r['frequency_hz']) or r['frequency_hz']<=0 for r in [*points,holdout]):raise ValueError('positive finite native frequencies required')
    if any(b['frequency_hz']<=a['frequency_hz'] for a,b in zip(points,points[1:])):raise ValueError('declared increasing tuning direction not supported')
    neighbors=[(a,b) for a,b in zip(points,points[1:]) if a['fine']<holdout['fine']<b['fine']]
    if len(neighbors)!=1:raise ValueError('holdout must lie strictly inside a measured bracket')
    a,b=neighbors[0];t=(holdout['fine']-a['fine'])/(b['fine']-a['fine']);predictions={'linear_frequency':a['frequency_hz']+(b['frequency_hz']-a['frequency_hz'])*t,'linear_period':1/((1-t)/a['frequency_hz']+t/b['frequency_hz'])}
    exact=[r for r in points if r['frequency_hz']==target_hz];brackets=[(a,b) for a,b in zip(points,points[1:]) if a['frequency_hz']<target_hz<b['frequency_hz']]
    target=dict(target_hz=target_hz,measured_bracket_available=bool(exact or brackets))
    if exact:target.update(lower=exact[0],upper=exact[0],exact_measured_point=True)
    elif brackets:target.update(lower=brackets[0][0],upper=brackets[0][1],exact_measured_point=False)
    return dict(fit_points=points,target=target,independent_holdout=dict(measured=holdout,bracket=[a,b],predictions=[dict(interpolation=k,predicted_frequency_hz=v,error_ppm=1e6*(v/holdout['frequency_hz']-1)) for k,v in predictions.items()]),interpolation_accuracy_characterized=True,interpolation_accuracy_accepted=False)

def run(family,output,wait):
    protocol_file=family/'protocol.json';submitted=family/'assessment.json';p=json.loads(protocol_file.read_text());a=json.loads(submitted.read_text());verify(p['input_sha256']);verify(a['input_sha256'])
    if not a['all_five_native_controllers_initialized']:raise ValueError('complete finite submission required')
    cases=[dict(fine=149,role='fit',native=p['existing_fine149_reference'],physical=p['existing_fine149_observer']),*a['submitted_cases']]
    if {r['fine'] for r in cases}!=set(p['fit_fine_codes'])|{p['independent_holdout_fine']}:raise ValueError('complete fit/holdout family required')
    model=[k for k in p['input_sha256'] if k.endswith('/backend_model.spice')]
    if len(model)!=1:raise ValueError('one full native backend required')
    files=[protocol_file,submitted,Path(__file__).resolve(),*[Path(__file__).with_name(n) for n in ['extract_keeper_replay_waveforms.py','common_v3.py','resources.py']]];pins={str(q):sha(q) for q in files};output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{31});save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())));save(output/'inputs.json',dict(input_sha256=pins,cases=cases,observation_cap_s=172800,automatic_identical_retry=False,release_ready=False));deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+172800
    try:
        while True:
            pending=[]
            for row in cases:
                for kind,terminal in [('native','flat_native_programming_transient_complete'),('physical','physical_tuning_voltage_assessment_complete')]:
                    base=Path(row[kind]);status=base/'status.json';owner_file=base/'owner.json'
                    if not status.exists() or not owner_file.exists():raise ValueError('initialized observer/native state required')
                    state=json.loads(status.read_text())['state']
                    if state=='stopped_without_qualification':raise RuntimeError(str(row['fine'])+' '+kind+' stopped without a usable result')
                    if state==terminal and(base/'assessment.json').exists():continue
                    owner=json.loads(owner_file.read_text())
                    if state!=terminal and identity(owner['pid'])!=owner['birth']:raise RuntimeError(str(row['fine'])+' '+kind+' owner is gone without completed receipt')
                    pending.append(dict(fine=row['fine'],stage=kind,state=state))
            if not pending:break
            if not wait:raise RuntimeError('characterization is still running')
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('characterization observation deadline; native children unchanged')
            save(output/'status.json',dict(state='waiting_for_completed_native_and_physical_points',pending=pending,release_ready=False));time.sleep(10)
        points=[]
        with lease(1,8,time.clock_gettime(time.CLOCK_BOOTTIME)+7200):
            for row in cases:
                native=Path(row['native']);physical=Path(row['physical']);nr=native/'assessment.json';pr=physical/'assessment.json';ci=native/'inputs.json';n,q,c=[json.loads(f.read_text()) for f in [nr,pr,ci]];completed_reference(n)
                for r in [n,q]:verify(r['input_sha256']);verify(r['artifacts'])
                if (c['coarse'],c['fine'],c['corner'],c['temperature_C'],c['supply_V'])!=(20,row['fine'],'tt',27,1.8) or c['input_sha256'].get(model[0])!=p['input_sha256'][model[0]]:raise ValueError('point has a different electrical domain')
                if q['input_sha256'].get(str(nr))!=sha(nr):raise ValueError('physical assessment belongs to a different native receipt')
                if not q['all_macro_and_DCO_tuning_bits_match'] or q['observed_bits']!=302 or q['observed_endpoint_voltages']!=604 or (q['coarse'],q['fine'])!=(20,row['fine']):raise ValueError('physical tuning word mismatch')
                f=n['frequency_diagnostic']
                if f is None:raise ValueError('completed native point has no frequency')
                points.append(dict(fine=row['fine'],frequency_hz=f['frequency_mhz']*1e6,role=row['role'],native_assessment=str(nr),physical_assessment=str(pr)))
                pins.update({str(f):sha(f) for f in [nr,pr,ci]})
        fit=[r for r in points if r['fine'] in p['fit_fine_codes']];held=[r for r in points if r['fine']==p['independent_holdout_fine']]
        if len(held)!=1:raise ValueError('one independent holdout required')
        metrics=characterize(fit,held[0]);verify(pins);save(output/'assessment.json',dict(input_sha256=pins,**metrics,all_native_and_physical_points_complete=True,coarse=20,corner='tt',temperature_C=27,supply_V=1.8,C_only_reference=True,distributed_wire_R_qualified=False,other_corners_qualified=False,closed_loop_qualified=False,model_qualified=False,release_ready=False));save(output/'status.json',dict(state='TT_native_curve_and_holdout_characterized',release_ready=False))
    except BaseException as e:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(e),native_children_unchanged=True,release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['family','output']:p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--wait',action='store_true');a=p.parse_args();run(a.family.resolve(),a.output.resolve(),a.wait)
