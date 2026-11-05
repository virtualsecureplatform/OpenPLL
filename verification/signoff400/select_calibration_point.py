"""Choose a native measurement, never an extrapolated simulation frequency."""
import argparse,json,math
from pathlib import Path
from common_v3 import save
from selected_model_registry import validate


def choose(points,coarse=20,target_hz=400e6):
    rows=sorted((p for p in points if p['coarse']==coarse),key=lambda p:p['fine'])
    if not rows or not math.isfinite(target_hz) or target_hz<=0:raise ValueError('measured coarse bank and positive target required')
    codes={p['fine'] for p in rows}
    if len(codes)!=len(rows):raise ValueError('duplicate measured code')
    for p in rows:
        if type(p['fine']) is not int or not 8<=p['fine']<=247 or not math.isfinite(p['frequency_hz']) or p['frequency_hz']<=0:raise ValueError('invalid measurement')
    base=dict(coarse=coarse,target_hz=target_hz,predictions_are_measurement_hints_only=True,release_ready=False)
    def request(code,reason):return dict(base,state='measurement_needed',fine=code,reason=reason)
    low=[r for r in rows if r['frequency_hz']<target_hz];high=[r for r in rows if r['frequency_hz']>target_hz]
    if low and high:
        pairs=[(a,b) for a in low for b in high];a,b=min(pairs,key=lambda pair:abs(pair[0]['fine']-pair[1]['fine']))
        lo,hi=sorted([a['fine'],b['fine']]);missing=[c for c in range(lo+1,hi) if c not in codes]
        if missing:return request(min(missing,key=lambda c:(abs(c-(lo+hi)/2),c)),'interior_native_holdout')
        return dict(base,state='target_bracket_observed',bracket_codes=[lo,hi],uncertainty_qualified=False)
    near=min(rows,key=lambda r:abs(r['frequency_hz']-target_hz))
    if len(rows)==1:
        for delta in [1,-1]:
            code=near['fine']+delta
            if 8<=code<=247:return request(code,'measure_local_tuning_direction')
    slopes=[(b['frequency_hz']-a['frequency_hz'])/(b['fine']-a['fine']) for a,b in zip(rows,rows[1:])]
    signs={1 if s>0 else -1 for s in slopes if s!=0}
    if len(signs)==1:
        other=min((r for r in rows if r!=near),key=lambda r:abs(r['fine']-near['fine']))
        slope=(near['frequency_hz']-other['frequency_hz'])/(near['fine']-other['fine'])
        if slope:
            estimate=near['fine']+(target_hz-near['frequency_hz'])/slope
            code=max(8,min(247,math.ceil(estimate) if estimate>near['fine'] else math.floor(estimate)))
            if code not in codes:return request(code,'secant_location_for_native_measurement')
    gaps=[(a['fine'],b['fine']) for a,b in zip(rows,rows[1:]) if b['fine']-a['fine']>1]
    if gaps:
        lo,hi=max(gaps,key=lambda pair:pair[1]-pair[0]);return request((lo+hi)//2,'resolve_flat_or_nonmonotonic_response')
    for code in [8,247]:
        if code not in codes:return request(code,'measure_bank_boundary')
    return dict(base,state='no_measured_target_bracket',requires_bank_or_design_review=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--registry',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():p.error('fresh output required')
    v=validate(json.loads(a.registry.read_text()));r=choose(v['points']);save(a.output,r);print(json.dumps(r))
