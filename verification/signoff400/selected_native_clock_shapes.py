"""Time-translate recorded native clock curves; never warp or extrapolate them."""
import bisect,json,math
from pathlib import Path
from common_v3 import save,sha,verify


def load(path):
    rows=[]
    with path.open() as stream:
        for line in stream:
            t,v=map(float,line.split())
            if not math.isfinite(t) or not math.isfinite(v) or (rows and t<=rows[-1][0]):raise ValueError('finite ordered source PWL required')
            rows.append((t,v))
    if len(rows)<2:raise ValueError('source PWL incomplete')
    return rows


def rising(rows,after):
    for (a,v),(b,w) in zip(rows,rows[1:]):
        if v<.9<=w:
            t=a+(.9-v)/(w-v)*(b-a)
            if t>=after:return t
    raise ValueError('complete native source rising edge required')


def shift_window(rows,shift,duration):
    times=[t for t,_ in rows];start=shift;stop=shift+duration
    if not math.isfinite(duration) or duration<=0 or not math.isfinite(shift) or start<times[0] or stop>times[-1]:raise ValueError('native source does not cover requested window; extrapolation forbidden')
    def value(t):
        i=bisect.bisect_left(times,t)
        if i<len(rows) and rows[i][0]==t:return rows[i][1]
        a,v=rows[i-1];b,w=rows[i];return v+(w-v)*(t-a)/(b-a)
    result=[(0.0,value(start))]
    result.extend((t-shift,v) for t,v in rows if start<t<stop)
    result.append((duration,value(stop)))
    return result


def prepare(folder,drives,phase_ns,output):
    receipt=folder/'assessment.json';a=json.loads(receipt.read_text());verify(a['artifacts'])
    if not a.get('exact_saved_knots_preserved') or not a.get('source_complete_and_all_values_finite'):raise ValueError('exact finite recorded native waveforms required')
    pins={str(receipt):sha(receipt),str(Path(__file__).resolve()):sha(Path(__file__))}
    waveforms={};details={}
    for role,key,after in [('reference','REF',0),('feedback','CLKDIVR',180e-9)]:
        item=a['clock_driver_waveforms'][key]
        if item['node']!=drives[role]:raise ValueError('native waveform is from a different physical voltage-input cut')
        path=Path(item['file']);pins[str(path)]=sha(path);rows=load(path)
        edge=rising(rows,after);target=(20+(phase_ns if role=='feedback' else 0))*1e-9;shift=edge-target
        shifted=shift_window(rows,shift,80e-9);dest=output/(role+'_native.pwl')
        with dest.open('x') as f:
            for t,v in shifted:f.write(f'{t:.17g} {v:.17g}\n')
        pins[str(dest)]=sha(dest);waveforms[role]=f'PWL FILE "{dest}"'
        details[role]=dict(source=str(path),native_rise_s=edge,target_first_source_rise_s=target,time_translation_s=shift,knots=len(shifted),voltage_values_approximated=False,time_warp_applied=False,extrapolation_applied=False)
    meta=output/'native_shape_construction.json';save(meta,dict(input_sha256=pins,clock_sources=details,
        native_feedback_frequency_offset_preserved=True,nominal_feedback_period_forced=False,
        waveform_construction_qualifies_interface=False,release_ready=False))
    pins[str(meta)]=sha(meta)
    return waveforms,pins
