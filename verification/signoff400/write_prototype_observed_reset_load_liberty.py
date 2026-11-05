"""Isolate reset-load sensitivity using finite native charge observations.

Only input capacitance numbers change. Native path correlation and measurement
uncertainty remain open; these views cannot qualify timing by themselves.
"""
import argparse
from collections import defaultdict
import json
import math
from pathlib import Path
from common_v3 import save,sha,verify
from write_prototype_load_envelope_liberty import rewrite


def preload_check(point,points):
    counts=[0,0]
    with (point/'batch.prn').open() as stream:
        next(stream)
        for line in stream:
            if not line.strip() or 'End of Xyce' in line:continue
            row=list(map(float,line.split()[1:]));t=row[0]
            mode=0 if 6.8e-9<=t<=7e-9 else (1 if 13e-9<=t<=14e-9 else None)
            if mode is None:continue
            counts[mode]+=1
            for i,record in enumerate(points):
                fixture=record['fixture']
                expected=fixture['data'] if mode==0 else int('__dfstp_' in fixture['master'])
                if abs(row[3+3*i]-expected*1.8)>.18:
                    raise ValueError('native preload or final asynchronous state differs')
    if min(counts)<2:raise ValueError('native state observation windows absent')
    return counts


def run(source,envelope,native,output):
    sr,er=[p/'assessment.json' for p in (source,envelope)]
    a,e=[json.loads(p.read_text()) for p in (sr,er)]
    for record in (a,e):verify(record['input_sha256']);verify(record['artifacts'])
    detail=envelope/'pin_capacitances.json'
    bounds={(r['master'],r['pin']):r for r in json.loads(detail.read_text())['pins']}
    pins=dict(a['input_sha256']);pins.update({str(p):sha(p) for p in (
        sr,er,detail,Path(__file__).resolve(),Path(__file__).with_name('write_prototype_load_envelope_liberty.py'))})
    observed=defaultdict(list);coverage=set();states=[];models=set()
    for point in native:
        receipt=point/'assessment.json';charge=point/'charge.json';model=point/'models.spice'
        r=json.loads(receipt.read_text());verify(r['input_sha256']);verify(r['artifacts'])
        if not r['known_capacitor_charge_sign_and_units_pass'] or r['temperature_c']!=27 or r['supply_v']!=1.8:
            raise ValueError('controlled nominal native charge observations required')
        corner=r['corner'];preloaded=r.get('preloaded_output_states_exercised',False)
        if corner not in ('tt','ff','ss','sf','fs') or (corner,preloaded) in coverage:
            raise ValueError('duplicate or unsupported charge observation')
        coverage.add((corner,preloaded));models.add(sha(model))
        rows=json.loads(charge.read_text())['points']
        if len(rows)!=60 or r['measured_reset_fixtures']!=60:
            raise ValueError('complete five-master charge grid required')
        if preloaded:states.append(dict(corner=corner,state_observation_counts=preload_check(point,rows)))
        for row in rows:
            f=row['fixture'];master=f['master'].removesuffix('__final_C');key=(master,f['control'])
            if key not in bounds:raise ValueError('native reset input absent from source timing view')
            values=[row[k]*1e12 for k in ('rising_20_80_effective_f','falling_80_20_effective_f')]
            if any(not math.isfinite(v) or v<=0 for v in values):raise ValueError('positive finite reset charge required')
            observed[corner,key].extend(values)
        for path in (receipt,charge,model,point/'batch.prn'):pins[str(path)]=sha(path)
    if len(models)!=1 or coverage!={(c,p) for c in ('tt','ff','ss','sf','fs') for p in (False,True)}:
        raise ValueError('matched models and static/preloaded observations in all five corners required')
    output.mkdir(parents=True,exist_ok=False);artifacts={};changes=[]
    for corner in ('tt','ff','ss','sf','fs'):
        local={key:dict(row) for key,row in bounds.items()}
        reset_keys={key for c,key in observed if c==corner}
        if len(reset_keys)!=5:raise ValueError('all five sequential reset masters required')
        for key in reset_keys:
            local[key]['supplied_minimum_pf']=min(observed[corner,key])
            local[key]['supplied_maximum_pf']=max(observed[corner,key])
        for edge in ('early','late'):
            path=source/f'{corner}_{edge}.lib'
            text,rows=rewrite(path.read_text(),local,edge)
            text=text.replace('Input loads use supplied-library sensitivity bounds; diode loads remain conditional TT data.',
                'Reset loads use finite native charge observations; other loads use supplied sensitivity bounds; diode loads remain conditional TT data.')
            target=output/path.name;target.write_text(text)
            pins[str(path)]=sha(path);artifacts[str(target)]=sha(target)
            changes.append(dict(corner=corner,view=edge,pins=rows))
    proof=output/'changes.json';save(proof,dict(changes=changes,preload_states=states));artifacts[str(proof)]=sha(proof)
    verify(pins);result=dict(a)
    result.update(input_sha256=pins,artifacts=artifacts,supplied_TT25_pin_capacitances_used=False,
        native_observed_reset_charge_bounds_used=True,all_five_corner_preload_states_verified=True,
        non_reset_inputs_use_broad_supplied_sensitivity_bounds=True,all_non_input_load_library_content_preserved=True,
        observed_charge_intervals_are_certified_impedance_bounds=False,
        native_PVT_pin_capacitance_and_routed_path_correlation_complete=False,
        screening_envelope_only=True,physical_timing_qualified=False,release_ready=False)
    save(output/'assessment.json',result)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('source','envelope','output'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--native-point',type=Path,required=True,action='append')
    args=parser.parse_args();run(args.source.resolve(),args.envelope.resolve(),[p.resolve() for p in args.native_point],args.output.resolve())
