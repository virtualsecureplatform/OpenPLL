"""Assess the prospectively selected static target without refitting the endpoint curves."""
import json
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from selected_static_DCO_point import measured_point


def run():
    base=ROOT/'build/signoff400';output=base/'selected_keeper_static_target_prediction_1554'
    output.mkdir(exist_ok=False)
    plan=base/'selected_keeper_static_target_plan_1548/plan.json'
    p=json.loads(plan.read_text());verify(p['input_sha256'])
    target=Path(p['independent_native_output'])/'assessment.json'
    record=json.loads(target.read_text());verify(record['input_sha256']);verify(record['artifacts'])
    coarse,fine,frequency_mHz=measured_point(target)
    if (coarse,fine)!=(p['coarse'],p['prediction']['selected_fine']):raise ValueError('predeclared independent point required')
    measured=frequency_mHz/1000
    endpoints=[base/'selected_keeper_static_coarse23_fine8_DCO_1545/assessment.json',
               base/'selected_keeper_static_coarse23_DCO_1541/assessment.json']
    values=[measured_point(r) for r in endpoints]
    x0,x1=values[0][1],values[1][1];f0,f1=values[0][2]/1000,values[1][2]/1000
    linear_frequency=p['prediction']['predicted_frequency_Hz']
    linear_period=1/(1/f0+(fine-x0)/(x1-x0)*(1/f1-1/f0))
    curves=[dict(kind=name,predicted_Hz=frequency,prediction_relative_to_measured_ppm=(frequency/measured-1)*1e6)
            for name,frequency in [('linear_frequency',linear_frequency),('linear_period',linear_period)]]
    files=[plan,target,*endpoints,Path(__file__).resolve(),Path(__file__).with_name('selected_static_DCO_point.py')]
    save(output/'assessment.json',dict(input_sha256={str(f):sha(f) for f in files},artifacts={},
         coarse=coarse,fine=fine,measured_Hz=measured,target_Hz=p['prediction']['target_Hz'],
         measured_relative_to_target_ppm=(measured/p['prediction']['target_Hz']-1)*1e6,
         predeclared_fit_codes=p['fit_fine_codes'],independent_validation_code=fine,curves=curves,
         endpoint_curves_refitted=False,holdout_used_as_global_error_bound=False,
         model_error_bound_qualified=False,full_layout_calibration_qualified=False,release_ready=False))


if __name__=='__main__':run()
