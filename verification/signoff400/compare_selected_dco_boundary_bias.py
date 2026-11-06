"""Compare normally completed same-circuit DCO quiet-boundary controls."""
import argparse,json,os,time
from pathlib import Path
from common_v3 import save,sha,verify
from resources import identity
from compare_selected_dco_load_controls import canonical_deck
from assess_selected_detector_prefix import read_prefix
from compare_selected_dco_startup_aligned_v5 import aligned,metrics
from audit_selected_dco_history_inputs import sources

def run(baseline,target,output,wait=False):
    os.sched_setaffinity(0,{30});output.mkdir(parents=True,exist_ok=False)
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+12600
    try:
        while True:
            state=json.loads((target/'status.json').read_text())['state']
            if state=='real_driver_DCO_diagnostic_complete':break
            if state=='stopped_without_qualification':raise ValueError('target terminal without normal completion')
            if not wait:raise ValueError('normal target completion required')
            owner=json.loads((target/'owner.json').read_text())
            if identity(owner['pid'])!=owner['birth']:raise RuntimeError('target controller disappeared')
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('observer deadline; native unchanged')
            save(output/'status.json',dict(state='waiting_for_native_boundary_bias_control',release_ready=False));time.sleep(10)
        if json.loads((baseline/'status.json').read_text())['state']!='real_driver_DCO_diagnostic_complete':
            raise ValueError('normal baseline completion required')
        manifests=[];assessments=[];waves=[];pins={}
        for folder in (baseline,target):
            m=json.loads((folder/'manifest.json').read_text());a=json.loads((folder/'assessment.json').read_text())
            verify(m['input_sha256']);verify(a['input_sha256']);verify(a['artifacts'])
            if not a['native_exit_zero'] or a['input_sha256']!=m['input_sha256']:raise ValueError('complete pinned native result required')
            raw=folder/'control.raw'
            if a['artifacts'].get(str(raw))!=sha(raw):raise ValueError('native waveform identity missing')
            rows,info=read_prefix(raw,m['observed_roles'])
            if info['incomplete_final_sample_discarded'] or info['declared_samples']!=len(rows) or abs(rows[-1][0]-60e-9)>1e-18:
                raise ValueError('complete 60 ns native waveform required')
            edges,startup=aligned(rows,1,2)
            if startup['end_age_ns']<40:raise ValueError('complete common-age window required')
            waves.append((edges,startup));manifests.append(m);assessments.append(a)
            for name in ('manifest.json','assessment.json','devices.spice','sources.spice','control.spice','control.raw'):
                path=folder/name;pins[str(path)]=sha(path)
        a,b=manifests
        binaries=[{p:d for p,d in m['input_sha256'].items()if p.endswith('/Xyce')}for m in manifests]
        if len(binaries[0])!=1 or binaries[0]!=binaries[1]:raise ValueError('same native executable required')
        for key in ('controls','operating_point','observed_roles','selected_primitives','retained_passive_cards'):
            if a[key]!=b[key]:raise ValueError('same circuit and condition required: '+key)
        if sha(baseline/'devices.spice')!=sha(target/'devices.spice') or canonical_deck((baseline/'control.spice').read_text())!=canonical_deck((target/'control.spice').read_text()):
            raise ValueError('only prescribed quiet voltages may change')
        x,y=[sources(p/'sources.spice')for p in (baseline,target)]
        if x.keys()!=y.keys():raise ValueError('same boundary nodes required')
        if any(x[n][0]!=y[n][0]for n in x):raise ValueError('source identities changed')
        # Protect every non-quiet source using the recorded all-boundary quiet vectors.
        q=[json.loads((p/'exterior_final_voltages.json').read_text())for p in (baseline,target)]
        if q[0].keys()!=q[1].keys():raise ValueError('quiet vector inventory changed')
        changed=[n for n in x if x[n]!=y[n]]
        if any(n not in q[0] or float(x[n][1])!=q[0][n] or float(y[n][1])!=q[1][n]for n in changed):
            raise ValueError('a programming, reset or rail source changed')
        paths=[Path(__file__).resolve()]+[Path(__file__).with_name(n)for n in ('common_v3.py','resources.py','compare_selected_dco_load_controls.py','assess_selected_detector_prefix.py','compare_selected_dco_startup_aligned_v5.py','assess_selected_detector_phase_probe_v2.py','audit_selected_dco_history_inputs.py')]
        pins.update({str(p):sha(p)for p in paths});verify(pins)
        freq=[a['frequency']['frequency_mhz']for a in assessments]
        save(output/'assessment.json',dict(input_sha256=pins,normal_native_completions=True,frequency_mhz=freq,
            frequency_change_ppm=1e6*(freq[1]/freq[0]-1),common_age_comparisons=metrics(waves[1][0],waves[0][0],40),
            first_output_rise_difference_ps=1000*(waves[1][1]['first_oscillator_rise_ns']-waves[0][1]['first_oscillator_rise_ns']),
            changed_quiet_sources=len(changed),scope='Combined held exterior corner and state change, TT final to matching corner reset state. Not an isolated corner effect or a uniform dynamic boundary uncertainty bound.',
            exterior_switching_qualified=False,whole_model_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='native_boundary_bias_sensitivity_assessed',release_ready=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('baseline','target','output'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--wait',action='store_true');a=p.parse_args()
    run(*(getattr(a,n).resolve()for n in ('baseline','target','output')),a.wait)
