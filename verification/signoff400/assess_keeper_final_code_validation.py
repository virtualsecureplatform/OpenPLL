"""Wait for completed final-code holdouts and compare frozen local predictions."""
import json,os,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import identity,lease
from selected_static_DCO_point import measured_point


def run():
    base=ROOT/'build/signoff400';output=base/'selected_keeper_final_code_validation_review_1560'
    output.mkdir(exist_ok=False);os.sched_setaffinity(0,{30})
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    plan=base/'selected_keeper_final_code_validation_plan_1556/plan.json'
    p=json.loads(plan.read_text());verify(p['input_sha256'])
    if p['fit_codes']!=[128,149] or p['validation_codes']!=[129,130,131] or not p['validation_codes_excluded_from_fits']:
        raise ValueError('frozen local fits and three independent code holdouts required')
    sources=[Path(case['output']) for case in p['cases']]
    pins={str(plan):sha(plan),str(Path(__file__).resolve()):sha(Path(__file__).resolve()),
          str(Path(__file__).with_name('selected_static_DCO_point.py')):sha(Path(__file__).with_name('selected_static_DCO_point.py'))}
    save(output/'inputs.json',dict(input_sha256=pins,observation_cap_s=86400,
         maximum_captures_observed=3,existing_jobs_modified=False,release_ready=False))
    try:
        deadline=time.monotonic()+86400
        while True:
            pending=[]
            for source in sources:
                state=json.loads((source/'status.json').read_text())['state']
                if state=='static_terminated_DCO_capture_complete':continue
                if state=='stopped_without_qualification':raise RuntimeError('native holdout stopped: '+str(source))
                owner=json.loads((source/'owner.json').read_text())
                if identity(owner['pid'])!=owner['birth']:raise RuntimeError('native holdout owner missing: '+str(source))
                pending.append(str(source))
            if not pending:break
            if time.monotonic()>=deadline:raise TimeoutError('holdout observation cap')
            save(output/'status.json',dict(state='waiting_for_completed_native_holdouts',pending=pending,release_ready=False));time.sleep(10)
        save(output/'status.json',dict(state='assessing_completed_native_holdouts',release_ready=False))
        comparisons=[]
        with lease(1,4,time.clock_gettime(time.CLOCK_BOOTTIME)+1800):
            for case,source in zip(p['cases'],sources):
                receipt=source/'assessment.json';coarse,fine,frequency_mHz=measured_point(receipt)
                if (coarse,fine)!=(case['coarse'],case['fine']):raise ValueError('holdout code differs from plan')
                measured=frequency_mHz/1000
                comparisons.append(dict(coarse=coarse,fine=fine,measured_Hz=measured,
                    primary_prediction_Hz=case['primary_linear_frequency_Hz'],
                    secondary_prediction_Hz=case['secondary_linear_period_Hz'],
                    primary_prediction_relative_to_measured_ppm=(case['primary_linear_frequency_Hz']/measured-1)*1e6,
                    secondary_prediction_relative_to_measured_ppm=(case['secondary_linear_period_Hz']/measured-1)*1e6,
                    measured_relative_to400MHz_ppm=(measured/400e6-1)*1e6))
                pins[str(receipt)]=sha(receipt)
        verify(pins)
        comparison=output/'comparison.json';save(comparison,comparisons)
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(comparison):sha(comparison)},
             fit_codes=[128,149],independent_validation_codes=[129,130,131],
             original_final_code_set=[128,129,130,131],original_final_code_set_now_directly_measured=True,
             maximum_sampled_primary_residual_ppm=max(abs(c['primary_prediction_relative_to_measured_ppm']) for c in comparisons),
             maximum_sampled_secondary_residual_ppm=max(abs(c['secondary_prediction_relative_to_measured_ppm']) for c in comparisons),
             original_gain_traces_changed_or_reassessed=False,holdouts_refitted=False,
             sampled_residuals_are_not_global_bounds=True,dynamic_code_step_response_qualified=False,
             full_layout_models_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='completed_native_holdouts_assessed',release_ready=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise


if __name__=='__main__':run()
