"""Simplify native clock PWLs under a verified uniform voltage-error bound.

Protect all 10/50/90 percent crossings and excursions between repeated
crossings. The error of two piecewise-linear curves is affine between their
combined knots; checking that union proves the global voltage bound. This
bounds voltage only, not derivative, charge, or detector-response error.
"""
import argparse,bisect,json,math
from pathlib import Path
from common_v3 import save,sha,verify
from selected_native_clock_shapes import load

LEVELS=(.18,.9,1.62)


def value(rows,t):
    times=[p[0] for p in rows];i=bisect.bisect_left(times,t)
    if i<len(rows) and times[i]==t:return rows[i][1]
    if i==0 or i==len(rows):raise ValueError('extrapolation forbidden')
    a,v=rows[i-1];b,w=rows[i];return v+(w-v)*(t-a)/(b-a)


def crossings(rows,level):
    result=[]
    for (a,v),(b,w) in zip(rows,rows[1:]):
        if v<level<=w or v>=level>w:result.append((a+(level-v)/(w-v)*(b-a),'rise' if w>v else 'fall'))
    return result


def simplify(rows,bound):
    if not math.isfinite(bound) or bound<=0 or bound>1e-6:raise ValueError('positive voltage error bound no larger than 1 uV required')
    if len(rows)<2 or any(not math.isfinite(x) for p in rows for x in p) or any(b[0]<=a[0] for a,b in zip(rows,rows[1:])):raise ValueError('finite strictly increasing PWL required')
    augmented=dict(rows);protected={rows[0][0],rows[-1][0]};original_crossings={}
    for level in LEVELS:
        events=crossings(rows,level);original_crossings[level]=events
        for t,_ in events:augmented[t]=level;protected.add(t)
        for (a,_),(b,_) in zip(events,events[1:]):
            between=[p for p in rows if a<p[0]<b]
            if between:
                t,v=max(between,key=lambda p:abs(p[1]-level));protected.add(t)
    points=sorted(augmented.items());indices={t:i for i,(t,_) in enumerate(points)};keep={indices[t] for t in protected};anchors=sorted(keep)
    stack=list(zip(anchors,anchors[1:]))
    while stack:
        first,last=stack.pop()
        if last-first<2:continue
        a,v=points[first];b,w=points[last]
        error,index=max((abs(y-(v+(w-v)*(t-a)/(b-a))),i) for i,(t,y) in enumerate(points[first+1:last],first+1))
        if error>bound:
            keep.add(index);stack.extend([(first,index),(index,last)])
    result=[points[i] for i in sorted(keep)]
    # Linear interpolation on both curves gives an exact union-knot certificate.
    times=sorted({t for t,_ in rows}|{t for t,_ in result})
    original_times=[t for t,_ in rows];result_times=[t for t,_ in result]
    def interpolate(curve,axis,t):
        i=bisect.bisect_left(axis,t)
        if i<len(curve) and axis[i]==t:return curve[i][1]
        a,v=curve[i-1];b,w=curve[i];return v+(w-v)*(t-a)/(b-a)
    maximum=max(abs(interpolate(rows,original_times,t)-interpolate(result,result_times,t)) for t in times)
    if maximum>bound*(1+1e-9)+1e-15:raise ValueError('uniform voltage error certificate failed')
    timing=[]
    for level in LEVELS:
        before=original_crossings[level];after=crossings(result,level)
        if len(before)!=len(after) or [d for _,d in before]!=[d for _,d in after]:raise ValueError('threshold crossing sequence changed')
        errors=[abs(a-b) for (a,_),(b,_) in zip(before,after)]
        if max(errors,default=0)>1e-18:raise ValueError('threshold crossing time changed')
        timing.append(dict(level_V=level,crossings=len(before),maximum_crossing_time_difference_s=max(errors,default=0)))
    return result,dict(original_knots=len(rows),bounded_knots=len(result),maximum_voltage_difference_V=maximum,
        uniform_voltage_bound_V=bound,union_knot_voltage_certificate=True,threshold_crossings=timing,
        voltage_derivative_equivalence_proven=False,charge_error_bounded=False,detector_response_equivalence_proven=False)


def prepare(paths,output,bound=1e-6):
    output.mkdir(parents=True,exist_ok=False);pins={str(Path(__file__).resolve()):sha(Path(__file__)),str(Path(__file__).with_name('selected_native_clock_shapes.py')):sha(Path(__file__).with_name('selected_native_clock_shapes.py'))};records={};waveforms={};artifacts={}
    for role,path in paths.items():
        rows=load(path);reduced,record=simplify(rows,bound);dest=output/(role+'_bounded.pwl')
        with dest.open('x') as f:
            for t,v in reduced:f.write(f'{t:.17g} {v:.17g}\n')
        if load(dest)!=reduced:raise ValueError('PWL serialization changed certified values')
        pins[str(path)]=sha(path);artifacts[str(dest)]=sha(dest);records[role]=dict(source=str(path),bounded_file=str(dest),**record)
        waveforms[role]=f'PWL FILE "{dest}"'
    verify(pins);receipt=output/'assessment.json'
    save(receipt,dict(input_sha256=pins,artifacts=artifacts,clock_sources=records,source_waveforms_approximated=True,
        threshold_levels_V=list(LEVELS),native_response_holdouts_complete=False,physical_models_qualified=False,release_ready=False))
    return waveforms,dict(pins,**artifacts,**{str(receipt):sha(receipt)})


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['reference','feedback','output']:p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--maximum-error-V',type=float,default=1e-6);a=p.parse_args()
    prepare(dict(reference=a.reference.resolve(),feedback=a.feedback.resolve()),a.output.resolve(),a.maximum_error_V)
    print(json.dumps(json.loads((a.output/'assessment.json').read_text())['clock_sources']))
