"""Extract complete native boundary waveforms into disk-backed arrays, never from a live RAW."""
import argparse,itertools,json,math,warnings
from pathlib import Path
import numpy as np
from common_v3 import save,sha,verify
from plan_keeper_conditional_replay import bind_variables

def completed_reference(a):
    required=['normal_native_completion','all_saved_native_values_finite','all_node_voltages_requested','stationary_requested_code']
    if not all(a.get(k) is True for k in required):raise ValueError('normally completed all-voltage stationary reference required')

def extract(raw,records,target,end_time):
    with raw.open() as stream:
        declared=count=None
        for line in stream:
            if line.startswith('No. Variables:'):declared=int(line.split(':',1)[1])
            if line.startswith('No. Points:'):count=int(line.split(':',1)[1])
            if line.strip()=='Variables:':break
        if declared is None or count is None or declared<2 or count<2:raise ValueError('complete positive native header required')
        names=[]
        for line in stream:
            if line.strip()=='Values:':break
            f=line.split()
            if len(f)!=3 or int(f[0])!=len(names):raise ValueError('invalid variable ordering')
            names.append(f[1])
        if len(names)!=declared or names[0].lower()!='time':raise ValueError('complete native variable header required')
        bound=bind_variables(records,names);ordered=list(records);indices=np.array([bound[n]['RAW_index'] for n in ordered],dtype=np.int64)
        matrix=np.lib.format.open_memmap(target,mode='w+',dtype=np.float64,shape=(count,1+len(ordered)))
        previous=-1.;samples=0
        for line in stream:
            if not line.strip():continue
            f=line.split()
            if len(f)!=2 or int(f[0])!=samples or samples>=count:raise ValueError('invalid sample index')
            t=float(f[1])
            if not math.isfinite(t) or t<=previous:raise ValueError('strictly increasing finite time required')
            raw_values=list(itertools.islice(stream,declared-1))
            if len(raw_values)!=declared-1:raise ValueError('truncated native values')
            # Each voltage occupies one RAW line. Parse in C while retaining one sample in memory.
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter('error',DeprecationWarning)
                    values=np.fromstring(''.join(raw_values),sep=' ',dtype=np.float64)
            except DeprecationWarning as e:raise ValueError('malformed saved voltage') from e
            if len(values)!=declared-1 or not np.isfinite(values).all():raise ValueError('incomplete or nonfinite saved voltage')
            matrix[samples,0]=t;matrix[samples,1:]=values[indices-1]
            previous=t;samples+=1
        if samples!=count or matrix[0,0]!=0 or abs(previous-end_time)>1e-18:raise ValueError('native waveform is truncated')
        matrix.flush();del matrix
    return dict(samples=samples,native_variables=declared,stored_columns=1+len(ordered),ordered_physical_ports=ordered,bindings=bound,all_saved_native_values_finite=True,storage='float64 NPY, sample-major, time in column zero',end_time_s=end_time)

def run(reference,plan,output):
    receipt=reference/'assessment.json';a=json.loads(receipt.read_text());completed_reference(a)
    verify(a['input_sha256']);verify(a['artifacts'])
    plan_receipt=plan/'assessment.json';p=json.loads(plan_receipt.read_text());verify(p['input_sha256']);verify(p['artifacts'])
    if p['reference_instance']!='XDUT' or not p['PLLOUT_forcing_forbidden']:raise ValueError('checked free-output replay plan required')
    full_model=next(k for k in p['input_sha256'] if k.endswith('/model.spice'))
    if a['input_sha256'].get(full_model)!=p['input_sha256'][full_model]:raise ValueError('reference uses another full model')
    ports=plan/'ports.json';raw=reference/'transient.raw'
    if str(raw) not in a['artifacts']:raise ValueError('completed RAW artifact hash required')
    files=[receipt,plan_receipt,ports,raw,Path(__file__).resolve(),Path(__file__).with_name('plan_keeper_conditional_replay.py')];pins={str(q):sha(q) for q in files};output.mkdir(parents=True,exist_ok=False);array=output/'boundary.npy'
    try:
        metrics=extract(raw,json.loads(ports.read_text()),array,260e-9);verify(pins);save(output/'columns.json',metrics)
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(q):sha(q) for q in [array,output/'columns.json']},completed_boundary_waveforms_available=True,all_saved_native_values_finite=True,samples=metrics['samples'],native_variables=metrics['native_variables'],PLLOUT_is_observation_only=True,lossy_waveform_compression_applied=False,environment_validated=False,replay_executed=False,model_qualified=False,release_ready=False))
    except BaseException as e:
        save(output/'status.json',dict(state='extraction_failed_no_validated_boundary_data',reason=repr(e),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['reference','plan','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve() for n in ['reference','plan','output']))
