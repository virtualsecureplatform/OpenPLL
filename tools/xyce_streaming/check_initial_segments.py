"""Bound held-voltage bootstrap error using exact recorded initial PWL segments.

Reading a prefix's right guard does not extend that bench's declared run interval.
This estimates source voltage error only, not downstream charge/state error.
"""
import argparse,json,math,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'verification/signoff400'))
from common_v3 import save,sha,verify


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--receipt',required=True,type=Path)
    p.add_argument('--bootstrap-ps',type=float,default=1)
    p.add_argument('--output',required=True,type=Path)
    a=p.parse_args()
    if a.output.exists():p.error('fresh output required')
    dt=a.bootstrap_ps*1e-12
    if not math.isfinite(dt) or dt<=0:p.error('positive finite bootstrap required')
    receipt=json.loads(a.receipt.read_text())
    sources={k:v for k,v in receipt['artifacts'].items() if Path(k).suffix=='.pwl'}
    if len(sources)!=receipt['boundary_files']:raise ValueError('complete boundary inventory required')
    verify(sources)
    results=[]
    for path in sources:
        with Path(path).open() as f:
            t0,v0=map(float,next(f).split());t1,v1=map(float,next(f).split())
        if not all(map(math.isfinite,(t0,v0,t1,v1))) or t0!=0 or t1<dt:
            raise ValueError('initial right guard does not cover bootstrap')
        results.append(dict(path=path,first_guard_s=t1,voltage_at_zero_V=v0,
            voltage_at_guard_V=v1,held_bootstrap_error_V=abs(v1-v0)*dt/t1))
    verify(sources)
    worst=max(results,key=lambda r:r['held_bootstrap_error_V'])
    save(a.output,dict(boundary_files=len(results),bootstrap_s=dt,
        exactly_flat_initial_segments=sum(r['voltage_at_zero_V']==r['voltage_at_guard_V'] for r in results),
        nonflat_initial_segments=sum(r['voltage_at_zero_V']!=r['voltage_at_guard_V'] for r in results),
        maximum_held_bootstrap_voltage_error_V=worst['held_bootstrap_error_V'],worst=worst,
        nonzero_segments=[r for r in results if r['held_bootstrap_error_V']>0],
        input_sha256={str(a.receipt.resolve()):sha(a.receipt),str(Path(__file__).resolve()):sha(Path(__file__))},
        source_artifacts_sha256=sources,scope='initial recorded source segment only; no charge or state bound',
        selected_boundary_replay_qualified=False,release_ready=False))
    print(json.dumps(dict(boundary_files=len(results),worst=worst,
        nonflat_initial_segments=sum(r['held_bootstrap_error_V']>0 for r in results))))
