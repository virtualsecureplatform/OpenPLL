"""Choose one full-native target refinement; never synthesize a measured point."""
import math
from fractions import Fraction
from select_calibration_point import choose as unbracketed_hint

def choose(points,target_hz=400e6,limit_ppm=1000):
    if not math.isfinite(target_hz)or target_hz<=0 or not math.isfinite(limit_ppm)or limit_ppm<0:
        raise ValueError('finite positive target and nonnegative tolerance required')
    rows=sorted((p for p in points if p['coarse']==20),key=lambda p:p['fine'])
    if not rows:raise ValueError('measured coarse20 points required')
    for p in rows:
        if type(p['fine'])is not int or not 8<=p['fine']<=247 or not math.isfinite(p['frequency_hz'])or p['frequency_hz']<=0:
            raise ValueError('finite positive measured frequency and supported code required')
    if any(a['fine']>=b['fine']or a['frequency_hz']>=b['frequency_hz']for a,b in zip(rows,rows[1:])):
        raise ValueError('distinct strictly increasing measured bank required')
    nearest=min(rows,key=lambda p:(abs(p['frequency_hz']-target_hz),p['fine']))
    exact_error=(Fraction(str(nearest['frequency_hz']))/Fraction(str(target_hz))-1)*1000000
    error=float(exact_error)
    result=dict(coarse=20,target_hz=target_hz,nominal_limit_ppm=limit_ppm,
        nearest_measured_code=nearest['fine'],nearest_measured_error_ppm=error,
        predicted_frequency_assigned=False,target_bracket_and_startup_headroom_qualified=False,release_ready=False)
    if abs(exact_error)<=Fraction(str(limit_ppm)):
        return dict(result,state='measured_nominal_target_observed',reason='skip_unnecessary_native_target_refinement')
    low=[p for p in rows if p['frequency_hz']<target_hz];high=[p for p in rows if p['frequency_hz']>target_hz]
    if low and high:
        a,b=low[-1],high[0];codes={p['fine']for p in rows}
        missing=[c for c in range(a['fine']+1,b['fine'])if c not in codes]
        if not missing:return dict(result,state='adjacent_target_bracket_requires_review',bracket_codes=[a['fine'],b['fine']])
        fa,fb,target=map(lambda x:Fraction(str(x)),(a['frequency_hz'],b['frequency_hz'],target_hz))
        hint=Fraction(a['fine'])+(target-fa)*(b['fine']-a['fine'])/(fb-fa)
        return dict(result,state='measurement_needed',fine=min(missing,key=lambda c:(abs(c-hint),c)),
            reason='native_measurement_nearest_bracket_secant_target',bracket_codes=[a['fine'],b['fine']],
            rational_code_hint=[hint.numerator,hint.denominator])
    hint=unbracketed_hint(rows,target_hz=target_hz)
    return dict(result,**{k:hint[k]for k in ('state','fine','reason')if k in hint},
        reason_scope='unbracketed secant/boundary hint for a new full-native measurement only')
