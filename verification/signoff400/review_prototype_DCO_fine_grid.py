"""Review measured tuning knots without qualifying unmeasured codes or final loading."""
import argparse
import json
from pathlib import Path
import time
from common_v3 import save,sha,verify
from prepare_prototype_loop_diagnostic import interpolate_period
from resources import lease

def run(grid,endpoints,output):
    pins={};groups={};identities=set();models=set()
    def merge(mapping):
        for name,digest in mapping.items():
            if name in pins and pins[name]!=digest:raise ValueError('conflicting evidence identity')
            pins[name]=digest
    def record(path):
        a=json.loads(path.read_text());merge({str(path):sha(path)});merge(a['input_sha256']);merge(a.get('artifacts',{}));return a
    authority=record(grid/'assessment.json')
    if authority.get('native_points_completed')!=70 or authority.get('failed_points')!=0:
        raise ValueError('completed seventy-point interior campaign required')
    points=[Path(r['point']) for r in json.loads((grid/'results.json').read_text())]
    if len(points)!=70 or any(authority['input_sha256'].get(str(p/'assessment.json'))!=sha(p/'assessment.json') for p in points):
        raise ValueError('campaign point authority mismatch')
    for point in points+endpoints:
        native=record(point/'assessment.json');review=record(point/'all_cycle_assessment/assessment.json')
        manifest=point/'input_manifest.json';m=json.loads(manifest.read_text());merge({str(manifest):sha(manifest)})
        if not native.get('native_worker_completed') or not review['all_captured_measurement_cycles_assessed']:
            raise ValueError('completed all-cycle native observation required')
        if review['input_sha256'].get(str(point/'assessment.json'))!=sha(point/'assessment.json') or review['input_sha256'].get(str(manifest))!=sha(manifest):
            raise ValueError('all-cycle native point binding differs')
        identities.update(d for p,d in native['input_sha256'].items() if p.endswith('.gds'))
        models.update((p,d) for p,d in native['input_sha256'].items() if p.endswith('/nom.spice'))
        metrics=point/'all_cycle_assessment/all_cycle_metrics.json';row=json.loads(metrics.read_text())
        if review['artifacts'].get(str(metrics))!=sha(metrics):raise ValueError('native observation changed')
        if any(row[key]!=native[key] or row[key]!=m[key] for key in ('corner','coarse_code','fine_code')):
            raise ValueError('operating point identity mismatch')
        key=(row['corner'],row['coarse_code']);code=row['fine_code']
        if code in groups.setdefault(key,{}):raise ValueError('duplicate native code')
        groups[key][code]=row
    if len(identities)!=1 or len(models)!=1:raise ValueError('one physical candidate and nominal RC model required')
    if {c for c,_ in groups}!={'tt','ff','ss','sf','fs'} or len(groups)!=5:
        raise ValueError('one band in each of five corners required')
    results=[];required={8,247,*range(24,233,16)}
    for (corner,coarse),knots in sorted(groups.items()):
        if set(knots)!=required:raise ValueError('complete sixteen-knot band required')
        rows=[knots[code] for code in sorted(knots)]
        monotone=all(a['observed_frequency_interval_hz'][1]<b['observed_frequency_interval_hz'][0] for a,b in zip(rows,rows[1:]))
        table={}
        for a,b in zip(rows,rows[1:]):table.update(interpolate_period(a,b))
        seed=min(table,key=lambda code:(abs(float(table[code])-400e6),code))
        results.append(dict(corner=corner,coarse_code=coarse,measured_codes=sorted(knots),
             sampled_frequency_intervals_strictly_increasing=monotone,
             observed_endpoint_bracket=rows[0]['observed_frequency_interval_hz'][1]<400e6<rows[-1]['observed_frequency_interval_hz'][0],
             interpolated_seed=seed,interpolated_seed_frequency_hz=float(table[seed]),
             fastest_observed_startup_or_measured_frequency_hz=max(r['fastest_observed_frequency_including_startup_hz'] for r in rows),
             native_seed_measurement_qualified=False,interior_codes_between_knots_qualified=False))
    with lease(1,4,time.clock_gettime(time.CLOCK_BOOTTIME)+43200):verify(pins)
    output.mkdir(parents=True,exist_ok=False);detail=output/'bands.json';save(detail,results)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(detail):sha(detail)},
         physical_GDS_sha256=next(iter(identities)),nominal_RC_identity=list(next(iter(models))),
         native_points_reviewed=80,measured_knots_per_corner=16,
         all_sampled_frequency_intervals_strictly_increasing=all(r['sampled_frequency_intervals_strictly_increasing'] for r in results),
         all_observed_endpoint_brackets=all(r['observed_endpoint_bracket'] for r in results),
         numerical_and_model_uncertainty_bounded=False,final_parent_loading_included=False,
         native_dynamic_control_response_qualified=False,analog_tuning_qualified=False,release_ready=False))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('grid','output'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--endpoint',type=Path,action='append',required=True)
    args=parser.parse_args();run(args.grid.resolve(),[p.resolve() for p in args.endpoint],args.output.resolve())
