"""Compare switched and separately initialized static tuning increments at equal ages.

No full-circuit switched reference is available: this reports a discrepancy,
not its cause or a qualified dynamic-model error bound.
"""
import argparse,json,math,os,time
from pathlib import Path
from common_v3 import save,sha,verify
from resources import lease
from assess_selected_detector_prefix import read_prefix
from assess_selected_isolated_control import frequency


def run(comparison,output):
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{24})
    a=json.loads(comparison.read_text());verify(a['input_sha256']);verify(a['artifacts'])
    if a['normal_native_completions'] is not True or a['driver_input_and_output_settled_states_verified'] is not True:raise ValueError('completed pulse and settled real driver required')
    manifests=[Path(p) for p in a['input_sha256'] if p.endswith('/manifest.json')]
    if len(manifests)!=3:raise ValueError('exact pulse and two static references required')
    tables={};pins={str(comparison):sha(comparison)}
    for path in manifests:
        m=json.loads(path.read_text());verify(m['input_sha256']);folder=path.parent
        if m['operating_point']!={'corner':'tt','supply_v':1.8,'temperature_c':27}:raise ValueError('same measured TT point required')
        if 'fine_sequence' in m:
            if m['fine_sequence']!=[111,112,111] or m['coarse']!=20:raise ValueError('original one-code pulse required')
            key='pulse';expected='checkpoint_code_step_diagnostic_complete'
        else:
            if m['controls']['coarse']!=20 or m['controls']['fine'] not in (111,112):raise ValueError('matching static reference pair required')
            key=m['controls']['fine'];expected='saved_state_DCO_diagnostic_complete'
        if key in tables or json.loads((folder/'status.json').read_text())['state']!=expected:raise ValueError('unique normally completed reference required')
        raw=folder/'control.raw'
        if a['input_sha256'].get(str(raw))!=sha(raw):raise ValueError('comparison waveform changed')
        with lease(1,2,time.clock_gettime(time.CLOCK_BOOTTIME)+300):rows,info=read_prefix(raw,m['observed_roles'])
        if info['incomplete_final_sample_discarded'] or rows[-1][0]<84e-9:raise ValueError('complete shared horizon required')
        tables[key]=rows
        for p in(path,raw,folder/'status.json'):pins[str(p)]=sha(p)
    if set(tables)!={'pulse',111,112}:raise ValueError('complete pulse/reference inventory required')
    windows=[]
    for start,stop in ((35,45),(40,55),(45,55),(50,59)):
        f={str(k):frequency(rows,start,stop) for k,rows in tables.items()}
        low=f['111']['frequency_mhz'];high=f['112']['frequency_mhz'];switched=f['pulse']['frequency_mhz'];static=high-low;dynamic=switched-low
        if not all(math.isfinite(v) for v in (low,high,switched)) or static<=0:raise ValueError('finite increasing static tuning reference required')
        windows.append(dict(window_ns=[start,stop],frequencies=f,static_increment_MHz=static,switched_increment_MHz=dynamic,switched_over_static_increment=dynamic/static,increment_difference_percent=(dynamic/static-1)*100,switched_minus_static112_ppm=(switched/high-1)*1e6))
    paths=[Path(__file__).resolve(),*(Path(__file__).with_name(n) for n in ('common_v3.py','resources.py','assess_selected_detector_prefix.py','assess_selected_isolated_control.py'))]
    pins.update({str(p):sha(p) for p in paths});verify(pins)
    report=output/'windows.json';save(report,windows)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(report):sha(report)},normal_native_completions=True,same_simulation_age_reference_windows=True,windows=windows,initial_and_returned_low_code_windows=a['windows'][::2],engineering_driver_ramp_ns=1,acceptance_limit=None,scope='One TT checkpoint partition with fixed exterior histories. Static references use their own measured initial states. No full-native switched-code reference; state dependence, exterior approximation and transient effects are not separated.',static_calibration_qualifies_switched_response=False,discrepancy_cause_identified=False,uniform_uncertainty_bound_qualified=False,full_circuit_dynamic_equivalence_qualified=False,release_ready=False))
    save(output/'status.json',dict(state='same_age_tuning_increments_assessed',release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('comparison','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.comparison.resolve(),a.output.resolve())
