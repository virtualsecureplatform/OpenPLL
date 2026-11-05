"""Evaluate measured frequency brackets with uncertainty; capture remains a separate obligation."""
import argparse
from fractions import Fraction as F
import json
from pathlib import Path
from common_v3 import PROFILE,save,sha,spec


def bracket(points,coarse,seed,increasing):
    profile=spec();low=profile['fine_code_min'];high=profile['fine_code_max']
    target=F(str(profile['target_mhz']))*10**6
    if type(coarse) is not int or not 0<=coarse<=47:raise ValueError('unsupported coarse code')
    if type(seed) is not int or not low<=seed<=high:raise ValueError('unsafe startup seed')
    if type(increasing) is not bool:raise ValueError('explicit tuning polarity required')
    measured={}
    for point in points:
        code=point['fine_code'];a=F(str(point['minimum_hz']));b=F(str(point['maximum_hz']))
        if type(code) is not int or not low<=code<=high or code in measured:
            raise ValueError('duplicate or unsupported measured fine code')
        if type(point['coarse_code']) is not int or point['coarse_code']!=coarse or not 0<a<=b:raise ValueError('wrong coarse code or invalid frequency interval')
        measured[code]=(a,b)
    if seed not in measured:raise ValueError('startup seed needs its own measured interval')
    below=[code for code,(a,b) in measured.items() if b<target]
    above=[code for code,(a,b) in measured.items() if a>target]
    candidates=[(a,b) for a in below for b in above if (a<b if increasing else b<a)]
    # Prefer the widest demonstrated code headroom. No precision/LSB gate is imposed.
    candidates.sort(key=lambda pair:(-abs(pair[1]-pair[0]),pair))
    chosen=next((pair for pair in candidates if min(pair)<=seed<=max(pair)),None)
    return dict(measured_target_bracket_contains_seed=chosen is not None,
        below_target_fine_code=chosen[0] if chosen else None,
        above_target_fine_code=chosen[1] if chosen else None,
        target_hz=str(target),coarse_code=coarse,startup_seed=seed,increasing=increasing,
        seed_frequency_interval_hz=[str(v) for v in measured[seed]],
        measured_points=len(measured),capture_under_uncertainty_verified=False,
        startup_waveform_and_frequency_coverage_verified=False,
        calibration_qualified=False)


def evaluate(data):
    profile=spec();results=[];seen=set()
    for corner in data['corners']:
        name=corner['corner']
        if name not in profile['corners'] or name in seen:raise ValueError('duplicate/unsupported process corner')
        if corner['temperature_c']!=27 or corner['supply_v']!=1.8:raise ValueError('unsupported calibration operating point')
        seen.add(name)
        results.append(dict(corner=name,**bracket(corner['points'],corner['coarse_code'],corner['seed'],corner['increasing'])))
    return dict(profile_sha256=sha(PROFILE),results=results,
        all_five_measured_brackets_contain_seeds=seen==set(profile['corners']) and all(r['measured_target_bracket_contains_seed'] for r in results),
        input_intervals_must_include='measurement, numerical-convergence and model/holdout uncertainty',
        native_provenance_verified=False,capture_under_uncertainty_verified=False,
        diagnostic=True,validated_for_prototype=False,release_ready=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--measurements',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.output.exists():p.error('fresh output required')
    result=evaluate(json.loads(a.measurements.read_text()));result['input_sha256']={str(a.measurements.resolve()):sha(a.measurements),str(Path(__file__).resolve()):sha(Path(__file__))}
    save(a.output,result)
