"""Validate electrical stimuli and observe resolution before the next clock edge."""
from assess_prototype_native_waveform import crossings

def analyze(rows,case):
    def edges(column,threshold):
        return crossings([(r[0],r[column]) for r in rows],threshold)
    rises,falls=edges(1,.9)
    if len(rises)!=10 or len(falls)!=10 or any(abs(t-n*1e-9)>1e-12 for t,n in zip(rises,range(10,30,2))) or any(abs(t-n*1e-9)>1e-12 for t,n in zip(falls,range(11,31,2))):
        raise ValueError('expected 500MHz clock train and one-ns high pulses')
    column=3 if case['kind']=='async_release' else 2
    direction=int(case['kind']=='data_fall')
    changed=edges(column,.9)[direction]
    if len(changed)!=1 or abs(changed[0]-(20+case['offset_ps']/1000)*1e-9)>1e-12:
        raise ValueError('one correctly phased changing input required')
    low=edges(column,.36)[direction];high=edges(column,1.44)[direction]
    if len(low)!=1 or len(high)!=1:
        raise ValueError('monotone input ramp required')
    window=[r for r in rows if 20e-9<=r[0]<=21.8e-9]
    final=[r[4] for r in window if r[0]>=21.5e-9]
    if not final or window[-1][0]<21.797e-9:
        raise ValueError('pre-next-edge observation missing')
    rail=0 if max(final)<.36 else 1 if min(final)>1.44 else None
    bad=[r[0] for r in window if rail==0 and r[4]>=.36 or rail==1 and r[4]<=1.44]
    step=max(b[0]-a[0] for a,b in zip(window,window[1:]))
    tail=None if rail is None else max(0.,((max(bad)+step) if bad else 20e-9)-20e-9)*1e9
    return dict(measured_changing_input_slew_20_to_80_ps=abs(high[0]-low[0])*1e12,
         observed_pre_next_edge_rail=rail,observed_resolution_ns_from_test_edge=tail,
         observation_end_ns=21.8,next_clock_rising_ns=22,
         next_clock_cannot_mask_observed_resolution=True,
         statistical_or_continuous_metastability_bound_proved=False)
