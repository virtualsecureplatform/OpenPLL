"""Observe the code-pulse completion and compare to both measured static codes."""
import argparse,json,os,time
from pathlib import Path
from common_v3 import save,sha,verify
from resources import identity,lease
from assess_selected_detector_prefix import read_prefix
from assess_selected_isolated_control import frequency
from assess_selected_detector_phase_probe_v2 import transitions


def run(pulse,low,high,output):
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{24})
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    try:
        owner=json.loads((pulse/'owner.json').read_text());deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+11100
        while True:
            state=json.loads((pulse/'status.json').read_text())['state']
            if state not in('preparing_checkpoint_code_step','checkpoint_code_step_native_running'):break
            if identity(owner['pid'])!=owner['birth']:raise ValueError('pulse controller stopped without normal completion')
            if time.clock_gettime(time.CLOCK_BOOTTIME)>deadline:raise TimeoutError('observer deadline; native unchanged')
            save(output/'status.json',dict(state='waiting_for_code_pulse',release_ready=False));time.sleep(10)
        if state!='checkpoint_code_step_diagnostic_complete':raise ValueError('normally completed pulse required')
        worker=json.loads((pulse/'native.process.json').read_text())
        if identity(worker['pid'])==worker['birth']:raise ValueError('native pulse worker still live')
        manifests=[json.loads((d/'manifest.json').read_text())for d in(pulse,low,high)]
        pm,lm,hm=manifests
        for m in manifests:verify(m['input_sha256'])
        if pm['coarse']!=20 or pm['fine_sequence']!=[111,112,111]or pm['changed_source_count']!=1:raise ValueError('declared one-code pulse required')
        for m,code in((lm,111),(hm,112)):
            if m['controls']['coarse']!=20 or m['controls']['fine']!=code or m['operating_point']!=pm['operating_point']:raise ValueError('matching TT coarse20 measured reference pair required')
        if pm['input_sha256'].get(str(low/'manifest.json'))!=sha(low/'manifest.json'):raise ValueError('pulse must derive from supplied low-code baseline')
        for d in(low,high):
            if json.loads((d/'status.json').read_text())['state']!='saved_state_DCO_diagnostic_complete':raise ValueError('normally completed static references required')
        paths=[Path(__file__).resolve(),*(Path(__file__).with_name(n)for n in('common_v3.py','resources.py','assess_selected_detector_prefix.py','assess_selected_isolated_control.py','assess_selected_detector_phase_probe_v2.py'))]
        paths += [d/name for d in(pulse,low,high)for name in('manifest.json','assessment.json','control.raw','status.json')]
        pins={str(p):sha(p)for p in paths}
        with lease(1,2,deadline):
            tables=[read_prefix(d/'control.raw',m['observed_roles'])for d,m in zip((pulse,low,high),manifests)]
        for (data,info),m in zip(tables,manifests):
            end=m.get('simulation_end_s',lm['simulation_end_s'])
            if info['incomplete_final_sample_discarded']or abs(data[-1][0]-end)>1e-18:raise ValueError('complete original restart horizons required')
        data=tables[0][0];windows=[]
        for start,stop,code in((15,25,111),(40,55,112),(70,84,111)):
            f=frequency(data,start,stop);ref=frequency(tables[1 if code==111 else 2][0],start,stop)
            voltage={}
            for role in('programming_driver_input','programming_driver_output'):
                index=list(pm['observed_roles']).index(role)+1;values=[r[index]for r in data if start<=r[0]*1e9<=stop]
                voltage[role]=dict(min_v=min(values),max_v=max(values))
                is_high=(code==112)==(role=='programming_driver_input')
                if (min(values)<1.62 if is_high else max(values)>.18):raise ValueError('physical programming driver failed to settle to expected state')
            windows.append(dict(window_ns=[start,stop],fine=code,pulse=f,static_reference=ref,
                difference_ppm=(f['frequency_mhz']/ref['frequency_mhz']-1)*1e6,observed_driver_voltages=voltage))
        edges=transitions(data,1)['rising_ns'];periods=[dict(midpoint_ns=(a+b)/2,period_ns=b-a)for a,b in zip(edges,edges[1:])if a>=20]
        detail=output/'instantaneous_periods.json';save(detail,periods);verify(pins)
        for m in manifests:verify(m['input_sha256'])
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(detail):sha(detail)},normal_native_completions=True,windows=windows,
            driver_input_and_output_settled_states_verified=True,engineering_input_ramp_ns=1,
            scope='One original TT checkpoint cut, engineering up/down pulse through actual programming driver. Static references use their own measured saved states. No full-native switched-code reference or extracted decoder hazard envelope.',
            full_circuit_dynamic_equivalence_qualified=False,uniform_model_uncertainty_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='code_pulse_response_assessed',release_ready=False))
    except BaseException as e:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(e),native_unchanged=True,release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in('pulse','low','high','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve()for n in('pulse','low','high','output')))
