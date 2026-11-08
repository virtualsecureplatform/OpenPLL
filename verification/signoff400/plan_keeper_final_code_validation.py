"""Predeclare native validation of interpolated codes visited in final TT lock windows."""
import json
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from selected_static_DCO_point import measured_point


def run():
    base=ROOT/'build/signoff400';output=base/'selected_keeper_final_code_validation_plan_1556'
    output.mkdir(exist_ok=False)
    review=base/'selected_keeper_fast_RTL_candidate_review_1555/assessment.json'
    r=json.loads(review.read_text());verify(r['input_sha256']);verify(r['artifacts'])
    if (r['TT_diagnostic_candidate'],r['cases_verified'],r['segments_verified'],r['final_windows_verified'],
            r['final_fine_min'],r['final_fine_max'])!=([1,2],12,20,80,128,131):
        raise ValueError('completed declared TT diagnostic code interval required')
    endpoints=[base/'selected_keeper_static_target_DCO_1549/assessment.json',
               base/'selected_keeper_static_coarse23_DCO_1541/assessment.json']
    points=[measured_point(p) for p in endpoints]
    if [(p[0],p[1]) for p in points]!=[(23,128),(23,149)]:raise ValueError('measured local fit endpoints required')
    f0,f1=[p[2]/1000 for p in points]
    cases=[]
    for fine,cpu,number in [(129,24,1557),(130,30,1558),(131,31,1559)]:
        fraction=(fine-128)/(149-128)
        destination=base/f'selected_keeper_static_fine{fine}_DCO_{number}'
        if destination.exists():raise FileExistsError('no duplicate case or overwrite')
        command=['/usr/bin/python3',str(ROOT/'verification/signoff400/run_keeper_static_DCO_point.py'),
                 '--output',str(destination),'--coarse','23','--fine',str(fine),'--cpu',str(cpu)]
        cases.append(dict(coarse=23,fine=fine,CPU=cpu,memory_GiB=8,output=str(destination),command=command,
            primary_linear_frequency_Hz=f0+fraction*(f1-f0),
            secondary_linear_period_Hz=1/(1/f0+fraction*(1/f1-1/f0))))
    files=[review,*endpoints,Path(__file__).resolve(),Path(__file__).with_name('run_keeper_static_DCO_point.py'),
           Path(__file__).with_name('selected_static_DCO_point.py')]
    save(output/'plan.json',dict(input_sha256={str(p):sha(p) for p in files},cases=cases,
         fit_codes=[128,149],validation_codes=[129,130,131],validation_codes_excluded_from_fits=True,
         observed_final_codes=[128,129,130,131],previous_gain_screen_modified=False,
         maximum_additional_native_cases=3,per_case_native_cap_s=86400,
         simulation_ns=60,max_step_ps=10,receiver_load_fF=32,
         automatic_identical_retry=False,model_error_bound_qualified=False,release_ready=False))


if __name__=='__main__':run()
