"""Fit directly measured lock codes and retain independent neighboring holdouts."""
import argparse
import json
from pathlib import Path
from common_v3 import save,sha,verify
from refine_prototype_loop_diagnostic_v2 import measurement_rc_identity,run as refine
from reseed_prototype_loop_diagnostic import run as reseed

def select_codes(frequencies,target=400e6):
    if len(frequencies)!=5 or sorted(frequencies)!=list(range(min(frequencies),max(frequencies)+1)):
        raise ValueError('five adjacent native codes required')
    seed=min(frequencies,key=lambda code:(abs(frequencies[code]-target),code))
    fit={seed-1,seed,seed+1}
    if not fit<=set(frequencies):raise ValueError('native neighborhood must extend beyond the selected seed')
    return seed,fit,set(frequencies)-fit

def table(path):
    rows=[line.split() for line in path.read_text().splitlines()]
    if not rows or any(len(row)!=3 for row in rows):raise ValueError('complete calibrated table required')
    result={int(row[1]):int(row[2])/1000 for row in rows}
    if len(result)!=len(rows):raise ValueError('duplicate frequency code')
    return result

def run(base,diagnostic,grid_points,native_points,output):
    old=json.loads(diagnostic.read_text());endpoint=json.loads(base.read_text())
    for model in (old,endpoint):verify(model['input_sha256'])
    if old['corner']!=endpoint['corner'] or old['coarse']!=endpoint['coarse'] or not old['synthetic'] or old['physical_models_qualified']:
        raise ValueError('matched unqualified grid and endpoint models required')
    pins={str(p):sha(p) for p in (base,diagnostic,Path(__file__).resolve(),Path(__file__).with_name('refine_prototype_loop_diagnostic_v2.py'),Path(__file__).with_name('reseed_prototype_loop_diagnostic.py'))}
    identities=set();native={};grid={}
    def read(point,long):
        receipt=point/'all_cycle_assessment/assessment.json';a=json.loads(receipt.read_text());verify(a['input_sha256']);verify(a['artifacts'])
        identities.add(measurement_rc_identity(receipt))
        metrics=point/'all_cycle_assessment/all_cycle_metrics.json';row=json.loads(metrics.read_text())
        manifest=point/'input_manifest.json';m=json.loads(manifest.read_text())
        if not a['all_captured_measurement_cycles_assessed'] or row['corner']!=old['corner'] or row['coarse_code']!=old['coarse']:
            raise ValueError('all-cycle operating-point identity differs')
        if long and (row['measurement_start_s']!=20e-9 or row['measurement_end_s']!=80e-9):
            raise ValueError('long native neighborhood observations required')
        pins.update({str(p):sha(p) for p in (receipt,metrics,manifest)})
        return row
    for point in grid_points:
        row=read(point,False);code=row['fine_code']
        if code in grid:raise ValueError('duplicate grid knot')
        grid[code]=(point,row)
    if set(grid)!=set(range(24,233,16)):raise ValueError('complete original interior grid required')
    for point in native_points:
        row=read(point,True);code=row['fine_code']
        if code in native:raise ValueError('duplicate long native code')
        native[code]=(point,row)
    if len(identities)!=1:raise ValueError('native and grid RC models differ')
    seed,fit,holdouts=select_codes({code:row['average_frequency_hz'] for code,(_,row) in native.items()})
    # A held-out code must not leak into the fitted table via the older short grid.
    omitted=set(grid)&set(native)
    selected=[point for code,(point,_) in grid.items() if code not in omitted]
    selected += [native[code][0] for code in sorted(fit)]
    output.mkdir(parents=True,exist_ok=False)
    refine(base,selected,output/'fit');reseed(output/'fit/models.json',output/'selected')
    model=json.loads((output/'selected/models.json').read_text())
    if model['seed']!=seed:raise ValueError('selected startup seed is not the directly measured nearest code')
    prior=table(Path(old['dco_table']));updated=table(Path(model['dco_table']));results=[]
    for code,(point,row) in sorted(native.items()):
        frequency=row['average_frequency_hz'];prediction=updated[code]
        results.append(dict(fine_code=code,point=str(point),used_for_fit=code in fit,independent_holdout=code in holdouts,
             native_average_frequency_hz=frequency,prior_prediction_hz=prior[code],updated_prediction_hz=prediction,
             prior_frequency_error_ppm=(prior[code]/frequency-1)*1e6,
             updated_frequency_error_ppm=(prediction/frequency-1)*1e6,
             updated_period_error_ps=(1/prediction-1/frequency)*1e12))
    detail=output/'correlation.json';save(detail,dict(points=results,omitted_short_grid_codes=sorted(omitted),
         omitted_short_grid_points=[str(grid[code][0]) for code in sorted(omitted)],
         historical_short_measurements_preserved=True,holdouts_excluded_from_fitted_table=True))
    for path in (output/'fit/assessment.json',output/'selected/assessment.json'):pins[str(path)]=sha(path)
    verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(detail):sha(detail),str(output/'selected/models.json'):sha(output/'selected/models.json')},
         corner=old['corner'],coarse_code=old['coarse'],selected_seed=seed,
         directly_measured_fit_codes=sorted(fit),independent_holdout_codes=sorted(holdouts),
         maximum_observed_holdout_period_error_ps=max(abs(r['updated_period_error_ps']) for r in results if r['independent_holdout']),
         maximum_observed_holdout_frequency_error_ppm=max(abs(r['updated_frequency_error_ppm']) for r in results if r['independent_holdout']),
         all_steady_codes_are_measured_if_loop_stays_within_fit_codes=True,
         numerical_uncertainty_bounded=False,final_parent_loading_complete=False,
         native_dynamic_control_response_qualified=False,physical_models_qualified=False,release_ready=False))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('base','diagnostic','output'):parser.add_argument('--'+name,type=Path,required=True)
    for name in ('grid-point','native-point'):parser.add_argument('--'+name,type=Path,required=True,action='append')
    args=parser.parse_args();run(args.base.resolve(),args.diagnostic.resolve(),[p.resolve() for p in args.grid_point],[p.resolve() for p in args.native_point],args.output.resolve())
