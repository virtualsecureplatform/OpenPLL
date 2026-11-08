"""Compare completed same-code native scopes without transferring timestep corrections."""
import json,os,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import identity,lease
from selected_static_DCO_point import measured_point
from queue_keeper_coarse23_center import checked_frequency


def run():
    base=ROOT/'build/signoff400';output=base/'selected_keeper_coarse23_native_scope_comparison_1562'
    output.mkdir(exist_ok=False);os.sched_setaffinity(0,{28})
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    parent=base/'selected_keeper_coarse23_central_campaign_1512'
    native=base/'selected_keeper_corrected_coarse23_fine149_step50_1513'
    controls=base/'selected_keeper_corrected_coarse23_physical_1514'
    fast=base/'selected_keeper_static_coarse23_DCO_1541/assessment.json'
    files=[parent/'plan.json',native/'inputs.json',fast,Path(__file__).resolve(),
           Path(__file__).with_name('selected_static_DCO_point.py'),Path(__file__).with_name('queue_keeper_coarse23_center.py')]
    pins={str(p):sha(p) for p in files}
    save(output/'inputs.json',dict(input_sha256=pins,coarse=23,fine=149,corner='tt',temperature_C=27,supply_V=1.8,
         full_max_step_ps=50,fast_max_step_ps=10,full_window_ns=[200,260],fast_window_ns=[20,60],
         observation_cap_s=86400,coarse20_correction_transfer=False,release_ready=False))
    try:
        deadline=time.monotonic()+86400
        while True:
            state=json.loads((parent/'status.json').read_text())['state']
            if state=='coarse23_central_capture_and_physical_checks_complete':break
            if state=='stopped_without_qualification':raise RuntimeError('full center campaign stopped')
            owner=json.loads((parent/'owner.json').read_text())
            if identity(owner['pid'])!=owner['birth']:raise RuntimeError('full center campaign owner missing')
            if time.monotonic()>=deadline:raise TimeoutError('full center observation cap')
            save(output/'status.json',dict(state='waiting_for_full_center_and_all604_controls',release_ready=False));time.sleep(10)
        save(output/'status.json',dict(state='checking_completed_native_scopes',release_ready=False))
        receipts=[parent/'assessment.json',native/'assessment.json',controls/'assessment.json']
        with lease(1,2,time.clock_gettime(time.CLOCK_BOOTTIME)+3600):
            records=[json.loads(p.read_text()) for p in receipts]
            for record in records:
                verify(record['input_sha256']);verify(record.get('artifacts',{}))
            full=checked_frequency(records[1],records[2],23)
            coarse,fine,millihertz=measured_point(fast)
            if (coarse,fine)!=(23,149):raise ValueError('same actual native tuning code required')
            domain=json.loads((native/'inputs.json').read_text())
            if tuple(domain[k] for k in ('corner','temperature_C','supply_V','coarse','fine','max_step_ps','simulation_ns'))!=('tt',27,1.8,23,149,50,260):
                raise ValueError('declared full native scope differs')
            fast_MHz=millihertz/1e9
        verify(pins);pins.update({str(p):sha(p) for p in receipts})
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={},coarse=23,fine=149,
             full_frequency_MHz=full,fast_frequency_MHz=fast_MHz,
             fast_relative_to_full_ppm=(fast_MHz/full-1)*1e6,
             full_macro_and_DCO_endpoints_checked=604,fast_native_DCO_leaves_checked=302,
             full_max_step_ps=50,fast_max_step_ps=10,timesteps_matched=False,
             startup_histories_matched=False,observation_windows_matched=False,
             full_wire_R_included=False,fast_wire_R_included=False,
             coarse20_timestep_correction_transferred=False,discrepancy_is_not_error_bound=True,
             model_correlation_qualified=False,target_bracket_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='completed_native_scopes_compared',release_ready=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise


if __name__=='__main__':run()
