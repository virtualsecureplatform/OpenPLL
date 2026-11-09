"""Predeclared adjacent-window diagnostic, not a physical settling proof."""
import math
from assess_selected_isolated_control import frequency


def assess_settling(rows):
    if not rows or rows[0][0]!=0 or abs(rows[-1][0]-340e-9)>1e-18:
        raise ValueError('complete 340 ns capture required')
    if any(len(r)<2 or not all(math.isfinite(v) for v in r) for r in rows):
        raise ValueError('finite native samples required')
    if any(b[0]<=a[0] for a,b in zip(rows,rows[1:])):raise ValueError('strict native ordering required')
    windows=[]
    for start in [220,240,260,280,300,320]:
        try:measurement=frequency(rows,start,start+20);reason=None
        except ValueError as error:measurement=None;reason=str(error)
        windows.append(dict(start_ns=start,stop_ns=start+20,measurement=measurement,unavailable_reason=reason))
    final=windows[-3:];available=all(w['measurement'] is not None for w in final)
    span=None
    if available:
        values=[w['measurement']['frequency_mhz'] for w in final]
        span=(max(values)/min(values)-1)*1e6
    return dict(windows=windows,final_three_windows_available=available,final_window_frequency_span_ppm=span,
                sample_stability_screen_limit_ppm=100,sample_stability_screen_pass=available and span<=100,
                local_LSB_resolution_checked=False,timestep_convergence_verified=False,
                physical_settling_qualified=False,model_qualified=False,release_ready=False)
