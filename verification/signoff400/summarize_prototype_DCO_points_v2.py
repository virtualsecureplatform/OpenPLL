"""Summarize completed native cycle observations without treating them as calibration qualification."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import identity


def summarize(rows):
    groups=defaultdict(list);seen=set()
    for row in rows:
        key=(row['corner'],row['coarse_code'],row['fine_code'])
        if key in seen:raise ValueError('duplicate native operating point')
        seen.add(key)
        a,b=row['observed_frequency_interval_hz']
        if not 0<a<=b:raise ValueError('invalid native frequency interval')
        groups[key[:2]].append(row)
    result=[]
    for (corner,coarse),points in sorted(groups.items()):
        below=[p['fine_code'] for p in points if p['observed_frequency_interval_hz'][1]<400e6]
        above=[p['fine_code'] for p in points if p['observed_frequency_interval_hz'][0]>400e6]
        result.append(dict(corner=corner,coarse_code=coarse,below_target_codes=sorted(below),above_target_codes=sorted(above),
                           observed_target_bracket=bool(below and above),
                           uncertainty_inclusive_target_bracket_verified=False,calibration_qualified=False))
    return result


def run(output,rc_model):
    output.mkdir(parents=True,exist_ok=False);base=ROOT/'build/signoff400';points=[];pending=[];pins={str(Path(__file__).resolve()):sha(Path(__file__).resolve())}
    pins[str(rc_model)]=sha(rc_model)
    for source in sorted(base.glob('prototype_v3_DCO_*_co*_fine*_001')):
        manifest=source/'input_manifest.json'
        if not manifest.exists():continue
        recorded=json.loads(manifest.read_text()).get('input_sha256',{})
        if recorded.get(str(rc_model))!=pins[str(rc_model)]:continue
        pins[str(manifest)]=sha(manifest)
        rp=source/'all_cycle_assessment/assessment.json';mp=rp.parent/'all_cycle_metrics.json'
        if not rp.exists():
            owner=source/'owner.json';status=source/'status.json'
            row=dict(directory=str(source))
            if status.exists():row['state']=json.loads(status.read_text())['state']
            if owner.exists():
                o=json.loads(owner.read_text());row['controller_live']=identity(o['pid'])==o['birth']
            pending.append(row);continue
        r=json.loads(rp.read_text());verify(r['input_sha256']);verify(r['artifacts'])
        if not r['all_captured_measurement_cycles_assessed'] or r['artifacts'].get(str(mp))!=sha(mp):raise ValueError('complete bound all-cycle assessment required')
        m=json.loads(mp.read_text())
        if (m['temperature_c'],m['supply_v'])!=(27,1.8) or m['complete_measured_cycles']<2:raise ValueError('unsupported native operating point')
        points.append(dict(directory=str(source),**{k:m[k] for k in ('corner','coarse_code','fine_code','average_frequency_hz','observed_frequency_interval_hz','fastest_observed_frequency_including_startup_hz','complete_measured_cycles')}))
        pins.update({str(p):sha(p) for p in (rp,mp)})
    detail=output/'points.json';save(detail,dict(completed=points,pending=pending,groups=summarize(points)));verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(detail):sha(detail)},completed_points=len(points),pending_points=len(pending),
         analog_RC_model_sha256=sha(rc_model),different_candidate_models_excluded=True,
         numerical_uncertainty_included=False,model_uncertainty_included=False,
         diagnostic=True,validated_for_prototype=False,release_ready=False))
    print('Completed points:',len(points),'pending:',len(pending))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True,type=Path);p.add_argument('--rc-model',required=True,type=Path);a=p.parse_args();run(a.output.resolve(),a.rc_model.resolve())
