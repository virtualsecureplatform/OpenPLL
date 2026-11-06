"""Compare terminal real-driver and full-native DCO startup frequencies.

Match oscillator age after the first rise following reset release, rather than
unrelated absolute simulation windows. Output observation points and reset
histories still differ, so this diagnostic cannot qualify a reduced model.
"""
import argparse,csv,json,math,os,time
from pathlib import Path
from common_v3 import save,sha,verify
from resources import identity
from selected_spice_device_conditions import matching,reference_deck
from assess_selected_detector_prefix import read_prefix
from assess_selected_detector_phase_probe_v2 import transitions


def window_frequency(edges,start,stop):
    selected=[t for t in edges if start<=t<=stop]
    if len(selected)<3:raise ValueError('at least three measured rises per common window required')
    periods=[b-a for a,b in zip(selected,selected[1:])]
    return dict(rising_edges=len(selected),frequency_mhz=1000/(sum(periods)/len(periods)),
                minimum_period_ns=min(periods),maximum_period_ns=max(periods))


def aligned(rows,output_column,reset_column):
    reset=transitions(rows,reset_column)['rising_ns']
    if len(reset)!=1:raise ValueError('exactly one observed reset release required')
    edges=[t for t in transitions(rows,output_column)['rising_ns'] if t>=reset[0]]
    if len(edges)<3:raise ValueError('at least three oscillator edges after reset required')
    return [t-edges[0] for t in edges],dict(reset_release_ns=reset[0],first_oscillator_rise_ns=edges[0],end_age_ns=rows[-1][0]*1e9-edges[0])


def metrics(candidate,reference,stop):
    if stop<=10:raise ValueError('common oscillator-age coverage missing')
    windows=[(10,stop),(10,(10+stop)/2),((10+stop)/2,stop)]
    results={}
    for key,(start,end) in zip(['common','early','late'],windows):
        c=window_frequency(candidate,start,end);r=window_frequency(reference,start,end)
        results[key]=dict(window_after_first_rise_ns=[start,end],candidate=c,full_native=r,
                          difference_ppm=1e6*(c['frequency_mhz']/r['frequency_mhz']-1))
    return results


def run(native,reference,reference_assessment,output,wait=False,reference_provenance=None,expected_end_ns=60):
    if output.exists():raise FileExistsError(output)
    if expected_end_ns not in [60,260]:raise ValueError('supported declared native duration required')
    owner=json.loads((native/'owner.json').read_text());deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+7500
    while True:
        state=json.loads((native/'status.json').read_text())
        if state['state'] not in ['preparing_real_driver_DCO_diagnostic','real_driver_DCO_native_running']:break
        if not wait:raise ValueError('native diagnostic remains live')
        if identity(owner['pid'])!=owner['birth']:raise ValueError('controller exited without terminal status')
        if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('observation deadline; original native job unchanged')
        time.sleep(10)
    complete=state['state']=='real_driver_DCO_diagnostic_complete'
    budget=state['state']=='stopped_without_qualification' and 'TimeoutError' in state.get('reason','')
    if not complete and not budget:raise ValueError('normal completion or terminal budget stop required')
    process=native/'native.process.json';p=json.loads(process.read_text())
    if identity(p['pid'])==p['birth']:raise ValueError('native worker still live')
    manifest=native/'manifest.json';m=json.loads(manifest.read_text());verify(m['input_sha256'])
    # Bind the full reference CSV to the completed assessment of its native run.
    a=json.loads(reference_assessment.read_text())
    coarse,fine=m['controls']['coarse'],m['controls']['fine']
    if a.get('end_ns')!=260 or a.get('coarse_code',{}).get('window_codes')!=[coarse] or a.get('dco_code',{}).get('window_codes')!=[fine]:raise ValueError('same native programming code and full 260 ns assessment required')
    if reference_provenance is None:raise ValueError('full reference provenance required')
    provenance=json.loads(reference_provenance.read_text());verify(provenance['input_sha256']);verify(provenance['artifacts'])
    if provenance['artifacts'].get(str(reference))!=sha(reference) or provenance['artifacts'].get(str(reference_assessment))!=sha(reference_assessment):raise ValueError('reference CSV and assessment must share native provenance')
    models={p:d for p,d in m['input_sha256'].items() if p.endswith('/model.spice')}
    if len(models)!=1 or any(provenance['native_input_sha256'].get(p)!=d for p,d in models.items()):raise ValueError('same native physical model required')
    physical_reference_deck=reference_deck(provenance)
    conditions=matching(native/'control.spice',physical_reference_deck)
    if m.get('operating_point',{}).get('corner')!=conditions['corner']:raise ValueError('declared candidate corner differs from native deck')
    with reference.open() as f:
        reader=csv.reader(f);names=next(reader);full=[[float(v) for v in row] for row in reader]
    if not full or full[0][0]!=0 or abs(full[-1][0]-260e-9)>1e-18 or any(len(row)!=len(names) or not all(math.isfinite(v) for v in row) for row in full) or any(b[0]<=a[0] for a,b in zip(full,full[1:])):raise ValueError('complete finite ordered full native waveform required')
    if a.get('samples')!=len(full):raise ValueError('full native assessed sample count mismatch')
    raw=native/'control.raw';rows,info=read_prefix(raw,m['observed_roles'])
    if complete and (info['incomplete_final_sample_discarded'] or abs(rows[-1][0]-expected_end_ns*1e-9)>1e-18):raise ValueError('normal completion without full declared waveform')
    c,cm=aligned(rows,1,2)
    r,rm=aligned(full,names.index('v(pllout)'),names.index('v(xpll:__parent_r_node_617)'))
    stop=min(40,cm['end_age_ns'],rm['end_age_ns']);result=metrics(c,r,stop)
    inputs=[Path(__file__).with_name('selected_spice_device_conditions.py'),native/'control.spice',physical_reference_deck,reference_provenance,manifest,native/'status.json',process,raw,reference,reference_assessment,Path(__file__).resolve(),Path(__file__).with_name('assess_selected_detector_prefix.py'),Path(__file__).with_name('assess_selected_detector_phase_probe_v2.py')]
    pins={str(p):sha(p) for p in inputs};verify(pins)
    output.mkdir(parents=True)
    save(output/'assessment.json',dict(input_sha256=pins,normal_full_window_completed=complete,native_budget_stopped=budget,expected_end_ns=expected_end_ns,
        candidate_waveform=info,coarse=coarse,fine=fine,device_conditions=conditions,candidate_startup=cm,full_native_startup=rm,frequency_comparisons=result,
        alignment='oscillator age after first observed output rise following reset release',
        exact_physical_observation_points_matched=False,reset_and_initial_history_matched=False,
        exterior_switching_qualified=False,receiver_loading_bounded=False,numerical_convergence_qualified=False,
        frequency_correlation_qualified=False,physical_models_qualified=False,release_ready=False))
    print(json.dumps(result))


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['native','reference','reference-assessment','output']:p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--reference-provenance',type=Path,required=True)
    p.add_argument('--wait',action='store_true');p.add_argument('--expected-end-ns',type=int,choices=[60,260],default=60);a=p.parse_args();os.sched_setaffinity(0,{30})
    run(*(getattr(a,n.replace('-','_')).resolve() for n in ['native','reference','reference-assessment','output']),a.wait,a.reference_provenance.resolve(),a.expected_end_ns)
