"""Three actual-controller mixed-signal startup diagnostics with static DCO knots."""
import json,os,time
from pathlib import Path
from common_v3 import ROOT,save,sha
from resources import lease
from run_startup_mixed_signal_1837 import run as simulate


def run():
    b=ROOT/'build/signoff400';out=b/'selected_startup_mixed_signal_1838';out.mkdir(exist_ok=False)
    receipts=[b/(n+'/assessment.json')for n in ['selected_keeper_static_coarse23_fine8_DCO_1545','selected_keeper_static_target_DCO_1549','selected_keeper_static_coarse23_DCO_1541','selected_keeper_static_fine129_DCO_1557','selected_keeper_static_fine130_DCO_1558','selected_keeper_static_fine131_DCO_1559']]
    detector=b/'selected_root_publication_detector_407/detector.v';clock=b/'selected_clock_phase_observations_187.json'
    os.sched_setaffinity(0,{24});os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
    results=[]
    with lease(1,2,time.clock_gettime(time.CLOCK_BOOTTIME)+600):
        for scenario in [0,1,2]:
            save(out/'status.json',dict(state='running_startup_scenario',scenario=scenario))
            r=simulate(receipts,detector,out/f'scenario_{scenario}',ki=1,kp=2,coarse=23,seed=128,polarity=1,scenario=scenario,phase_ns=0,clock_timing_path=clock,interpolation_kind='linear_frequency')
            results.append(dict(scenario=scenario,report=r))
    save(out/'assessment.json',dict(results=results,analog_models_qualified=False,full_RC_correlation_qualified=False,release_ready=False))
    save(out/'status.json',dict(state='mixed_signal_diagnostics_complete'))

if __name__=='__main__':run()
