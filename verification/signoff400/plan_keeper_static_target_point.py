"""Prospectively select one independent native point inside the fast-subsystem bracket."""
import json,math
from pathlib import Path
from common_v3 import ROOT,save,sha,verify


def select(x0,f0,x1,f1,target=400e6):
    if (type(x0) is not int or type(x1) is not int or not 8<=x0<x1<=247
            or not all(math.isfinite(v) and v>0 for v in (f0,f1,target))
            or not f0<target<f1):
        raise ValueError('strictly interior positive-frequency target in measured increasing bracket required')
    frequency_code=x0+(target-f0)*(x1-x0)/(f1-f0)
    period_code=x0+(1/target-1/f0)*(x1-x0)/(1/f1-1/f0)
    seed=math.floor(frequency_code+.5)
    if not x0<seed<x1:raise ValueError('independent interior integer code required')
    prediction=f0+(seed-x0)*(f1-f0)/(x1-x0)
    return dict(primary_interpolation='linear_frequency',secondary_interpolation='linear_period',
         continuous_frequency_code=frequency_code,continuous_period_code=period_code,
         selected_fine=seed,predicted_frequency_Hz=prediction,
         predicted_target_error_ppm=(prediction/target-1)*1e6,target_Hz=target)


def run():
    b=ROOT/'build/signoff400';output=b/'selected_keeper_static_target_plan_1548'
    output.mkdir(exist_ok=False)
    cases=[b/'selected_keeper_static_coarse23_fine8_DCO_1545',b/'selected_keeper_static_coarse23_DCO_1541']
    inputs=[];frequencies=[];files=[Path(__file__).resolve()]
    for case in cases:
        receipt=case/'assessment.json';record=json.loads(receipt.read_text())
        verify(record['input_sha256']);verify(record['artifacts'])
        source=case/'inputs.json';domain=json.loads(source.read_text())
        if not all(record[k] for k in ('normal_native_completion','all_saved_values_finite','all_native_DCO_leaves_match')):
            raise ValueError('completed finite native points with matching leaves required')
        if (domain['coarse'],domain['receiver_load_fF'],domain['simulation_ns'],domain['max_step_ps'])!=(23,32,60,10):
            raise ValueError('same declared static coarse23 model required')
        inputs.append(domain);frequencies.append(record['frequency_diagnostic']['frequency_mhz']*1e6)
        files.extend([receipt,source])
    common=[k for k in inputs[0]['input_sha256'] if k.endswith('/model.spice') or k.endswith('/Xyce')]
    if len(common)!=2 or any(inputs[0]['input_sha256'][k]!=inputs[1]['input_sha256'].get(k) for k in common):
        raise ValueError('identical native model and simulator required')
    prediction=select(inputs[0]['fine'],frequencies[0],inputs[1]['fine'],frequencies[1])
    save(output/'plan.json',dict(input_sha256={str(p):sha(p) for p in files},
         fit_fine_codes=[8,149],coarse=23,prediction=prediction,
         independent_native_output=str(b/'selected_keeper_static_target_DCO_1549'),
         CPU=31,memory_GiB=8,maximum_additional_native_cases=1,
         target_measurement_used_for_fit=False,automatic_identical_retry=False,
         extrapolation=False,full_layout_bracket_qualified=False,
         frequency_error_bound_qualified=False,release_ready=False))


if __name__=='__main__':run()
