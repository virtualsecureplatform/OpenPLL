"""Run conditional native loaded-path screens using the actual physical chain.

Four fixed receiver phase states and sensitized AOI inputs are diagnostics;
quiet exterior coupling and a sampled input slew do not qualify a uniform bound.
"""
import argparse
import json
import os
from pathlib import Path
import time

from common_v3 import ROOT, save, sha, verify
from resources import identity, lease
from compiled_charge_v2 import execute
from audit_selected_dco_final_bias import last_sample
from check_selected_boundary_waveforms import bind
from run_selected_detector_phase_probe_v5 import export
from assess_selected_detector_prefix import read_prefix


def crossings(rows, column, threshold, rising):
    result = []
    for a,b in zip(rows, rows[1:]):
        if (a[column] < threshold <= b[column]) if rising else (a[column] > threshold >= b[column]):
            result.append((a[0]+(b[0]-a[0])*(threshold-a[column])/(b[column]-a[column]))*1e9)
    return [t for t in result if 3 <= t <= 18]


def slew(rows, column):
    result = {}
    for rising in (True, False):
        start, end = (.36, 1.44) if rising else (1.44, .36)
        a,b = crossings(rows,column,start,rising),crossings(rows,column,end,rising)
        if len(a) != 1 or len(b) != 1 or b[0] <= a[0]:
            raise ValueError('one complete monotonic-threshold edge in each direction required')
        result['rise_ps' if rising else 'fall_ps'] = (b[0]-a[0])*1000
    return result


def run(plan, model, native, snapshot, image, output):
    os.sched_setaffinity(0,{27}); output.mkdir(parents=True,exist_ok=False)
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    save(output/'status.json',dict(state='preparing_loaded_programming_path',release_ready=False))
    try:
        p=json.loads(plan.read_text());verify(p['input_sha256'])
        if p['input_sha256'].get(str(model))!=sha(model):raise ValueError('same physical model required')
        s=json.loads(snapshot.read_text());verify(s['artifacts'])
        verify({k:v for k,v in s['input_sha256'].items() if not k.endswith('/profile.raw')})
        raw=native/'profile.raw';manifest=native/'manifest.json';m=json.loads(manifest.read_text())
        if s['input_sha256'].get(str(manifest))!=sha(manifest) or m['input_sha256'].get(str(model))!=sha(model):
            raise ValueError('native quiet-bias snapshot lineage differs')
        names,values=last_sample(raw,s['source_file_fingerprint'])
        nodes=p['required_non_supply_boundary_voltage_nodes'];bindings=bind(nodes,names)
        if not bindings['all_bound']:raise ValueError('all exterior boundaries require saved native voltages')
        quiet={n:values[bindings['bindings'][n]['index']] for n in nodes}
        devices=output/'devices.spice';export(model,p,devices)
        binary=ROOT/'build/tools/xyce_umfpack_value_gather_001/Xyce'
        paths=[plan,model,snapshot,manifest,image,devices,binary,Path(__file__).resolve()]
        paths += [Path(__file__).with_name(n) for n in ('resources.py','compiled_charge_v2.py','audit_selected_dco_final_bias.py','check_selected_boundary_waveforms.py','run_selected_detector_phase_probe_v5.py','assess_selected_detector_prefix.py','common_v3.py')]
        pins={str(x):sha(x) for x in paths};verify(pins)
        save(output/'manifest.json',dict(input_sha256=pins,CPU=27,memory_GiB=4,total_wall_limit_s=3600,
             corners=['tt','sf'],input_20_80_slew_ps=1000,receiver_phase_states=[[0,0],[0,1],[1,0],[1,1]],
             selected_primitives=len(p['selected_primitives']),passives=len(p['retained_passive_cards']),
             exterior_bias='retained full TT coarse20/fine111 final DC',release_ready=False))
        deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+3600;results=[];artifacts={}
        # Begin with the worst STA corner; TT provides a same-structure control.
        for corner in ('sf','tt'):
            for arc in ('A1','A2','B1'):
                for phase_a,phase_z in ((0,0),(0,1),(1,0),(1,1)):
                    folder=output/f'{corner}_{arc}_{phase_a}{phase_z}';folder.mkdir()
                    source=folder/'sources.spice';overrides={}
                    # 20--80% transition is 1 ns; a linear 0--100% ramp is 5/3 ns.
                    for pin,node in p['logic_inputs'].items():
                        value=1.8 if arc in ('A1','A2') and pin in ('A1','A2') and pin!=arc else 0
                        overrides[node]='PULSE(0 1.8 5n 1.66666666666667n 1.66666666666667n 5n 100n)' if pin==arc else str(value)
                    overrides.update({p['conditional_receiver_phase_pins']['A']:str(1.8*phase_a),p['conditional_receiver_phase_pins']['Z']:str(1.8*phase_z)})
                    if not set(overrides)<=set(nodes):raise ValueError('all stimulus cuts must be explicit boundaries')
                    with source.open('x') as stream:
                        for index,node in enumerate(nodes):stream.write(f'Vcut{index} {node} 0 {overrides.get(node,format(quiet[node],".17g"))}\n')
                        for index,(node,value) in enumerate([('VPWR',1.8),('VPB',1.8),('VGND',0),('VNB',0)]):stream.write(f'Vrail{index} {node} 0 {value}\n')
                    observed=p['observed_roles'];deck=folder/'profile.spice';waveform=folder/'profile.raw'
                    deck.write_text(f'Conditional actual loaded programming chain\n.lib "/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae/sky130A/libs.tech/ngspice/sky130.lib.spice" {corner}\n.include "{devices}"\n.include "{source}"\n.options parser model_binning=true\n.options device temp=27\n.options nonlin reltol=1e-5 abstol=1e-9\n.options timeint reltol=1e-5 abstol=1e-9\n.tran 2p 20n 0 2p\n.print tran format=raw precision=17 file={waveform} '+ ' '.join('v('+n+')' for n in observed.values())+'\n.end\n')
                    pins.update({str(x):sha(x) for x in (source,deck)})
                    save(output/'status.json',dict(state='native_loaded_programming_screen_running',case=folder.name,completed_cases=len(results),release_ready=False))
                    with lease(1,4,deadline):execute([binary,'-a','-linsolv','umfpack_reuse',deck],folder/'native.log',min(deadline,time.clock_gettime(time.CLOCK_BOOTTIME)+600),4)
                    rows,info=read_prefix(waveform,observed)
                    if info['incomplete_final_sample_discarded'] or abs(rows[-1][0]-20e-9)>1e-18:raise ValueError('complete native 20 ns waveform required')
                    measured={role:slew(rows,index+1) for index,role in enumerate(observed)}
                    results.append(dict(corner=corner,arc=arc,receiver_phase=[phase_a,phase_z],measured_slew=measured,waveform=info))
                    artifacts[str(waveform)]=sha(waveform);artifacts[str(folder/'native.log')]=sha(folder/'native.log')
        verify(pins);verify(artifacts)
        save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,results=results,
             all_24_native_cases_completed=True,sampled_input_20_80_slew_ps=1000,
             receiver_phase_conditioning_exhausts_static_binary_states=True,
             exterior_coupling_qualified=False,input_slew_range_qualified=False,
             loaded_programming_path_qualified=False,numerical_convergence_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='conditional_loaded_programming_screen_complete',release_ready=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('plan','model','native','snapshot','image','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve() for n in ('plan','model','native','snapshot','image','output')))
