"""Run a conditional full-derived DCO with its actual programming drivers.

Static programming is applied at real inverter inputs, never DCO control pins.
The first reset/output physical-cell halo and all incident passives are kept.
Quiet exterior voltages and remaining omitted loads limit this to diagnosis.
"""
import argparse,json,os,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import identity,lease
from compiled_charge_v2 import execute
from audit_selected_dco_final_bias import last_sample
from capture_selected_native_initial_snapshot import fingerprint
from check_selected_boundary_waveforms import bind
from run_selected_detector_phase_probe_v5 import export
from assess_selected_detector_prefix import read_prefix
from assess_selected_isolated_control import frequency


def run(plan,inventory,halo,model,native,snapshot,output,cpu):
    os.sched_setaffinity(0,{cpu});output.mkdir(parents=True,exist_ok=False)
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    save(output/'status.json',dict(state='preparing_real_driver_DCO_diagnostic',release_ready=False))
    try:
        pv,iv,hv=[json.loads(p.read_text()) for p in [plan,inventory,halo]]
        for v in [pv,iv,hv]:verify(v['input_sha256'])
        if pv['input_sha256'].get(str(inventory))!=sha(inventory) or pv['input_sha256'].get(str(halo))!=sha(halo) or pv['input_sha256'].get(str(model))!=sha(model):raise ValueError('partition/driver/halo/model identity mismatch')
        manifest=native/'manifest.json';nm=json.loads(manifest.read_text())
        if nm['input_sha256'].get(str(model))!=sha(model):raise ValueError('full native model mismatch')
        sr=json.loads(snapshot.read_text());verify(sr['artifacts']);verify({p:d for p,d in sr['input_sha256'].items() if not p.endswith('/profile.raw')})
        raw=native/'profile.raw'
        if str(raw) not in sr['input_sha256']:raise ValueError('verified full-native RAW provenance required')
        names,values=last_sample(raw,sr['source_file_fingerprint'])
        boundaries=pv['required_non_supply_boundary_voltage_nodes'];bound=bind(boundaries,names)
        if not bound['all_bound']:raise ValueError('all exterior nodes require native final voltages')
        quiet={n:values[bound['bindings'][n]['index']] for n in boundaries}
        controls={c['driver_input_node']:c['driver_input_for_final_bias_V'] for c in iv['controls'].values()}
        reset=pv['prescribed_reset_driver_input']
        if len(controls)!=302 or set(controls)!=set(pv['prescribed_control_driver_input_nodes']) or not reset or reset in controls:raise ValueError('complete independent programming and reset input cuts required')
        if not (set(controls)|{reset})<=set(boundaries):raise ValueError('all prescribed voltages must be on the circuit boundary')
        outputs=[e['node'] for n in hv['signal_interfaces'].values() for e in n['inside'] if e['direction']=='OUTPUT']
        reset_pins=[e['node'] for n in hv['signal_interfaces'].values() for e in n['inside'] if e['direction']=='INPUT']
        if len(outputs)!=1 or len(reset_pins)!=1:raise ValueError('unique DCO output and reset pin required')
        roles=dict(oscillator=outputs[0],DCO_reset=reset_pins[0],reset_driver_input=reset)
        if not {outputs[0],reset_pins[0]}<=set(pv['private_unknown_nodes']):raise ValueError('DCO output and reset must remain circuit unknowns')
        devices=output/'devices.spice';export(model,pv,devices)
        source=output/'sources.spice'
        with source.open('x') as f:
            for i,node in enumerate(boundaries):
                value='PULSE(0 1.8 5n 50p 50p 80n 160n)' if node==reset else format(controls.get(node,quiet[node]),'.17g')
                f.write(f'Vcut{i} {node} 0 {value}\n')
            for i,(node,value) in enumerate([('VPWR',1.8),('VPB',1.8),('VGND',0),('VNB',0)]):f.write(f'Vrail{i} {node} 0 {value}\n')
        save(output/'exterior_final_voltages.json',quiet)
        deck=output/'control.spice';waveform=output/'control.raw'
        deck.write_text(f'''Conditional full-derived DCO with real programming drivers
.lib "/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae/sky130A/libs.tech/ngspice/sky130.lib.spice" tt
.include "{devices}"
.include "{source}"
.options parser model_binning=true
.options device temp=27
.options nonlin reltol=1e-5 abstol=1e-9
.options timeint reltol=1e-5 abstol=1e-9
.tran 10p 60n 0 10p
.print tran format=raw precision=17 file={waveform} {' '.join('v('+n+')' for n in roles.values())}
.end
''')
        binary=ROOT/'build/tools/xyce_umfpack_value_gather_001/Xyce'
        paths=[plan,inventory,halo,model,manifest,snapshot,devices,source,deck,output/'exterior_final_voltages.json',binary,Path(__file__).resolve(),Path(__file__).with_name('audit_selected_dco_final_bias.py'),Path(__file__).with_name('capture_selected_native_initial_snapshot.py'),Path(__file__).with_name('check_selected_boundary_waveforms.py'),Path(__file__).with_name('run_selected_detector_phase_probe_v5.py'),Path(__file__).with_name('assess_selected_detector_prefix.py'),Path(__file__).with_name('assess_selected_isolated_control.py'),Path(__file__).with_name('compiled_charge_v2.py')]
        pins={str(p):sha(p) for p in paths};verify(pins)
        save(output/'manifest.json',dict(input_sha256=pins,CPU=cpu,memory_GiB=16,native_cap_s=7200,automatic_identical_retry=False,
            selected_primitives=len(pv['selected_primitives']),retained_passive_cards=len(pv['retained_passive_cards']),
            reference_raw_sha256=sr['input_sha256'][str(raw)],reference_raw_rehashed_this_run=False,
            reference_raw_file_fingerprint=sr['source_file_fingerprint'],observed_roles=roles,
            controls='coarse20 fine111; inverse fine; actual HS INV2 inputs driven',reset='5 ns pulse applied to actual CLKBUF4 input',
            exterior_condition='full native final 260 ns voltages held constant',remaining_omitted_primitive_load_count=len(pv['omitted_primitives_touching_private_nodes']),
            exterior_switching_qualified=False,receiver_loading_bounded=False,frequency_correlation_qualified=False,release_ready=False))
        deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+7200
        save(output/'status.json',dict(state='real_driver_DCO_native_running',release_ready=False))
        with lease(1,16,deadline):execute([binary,'-a','-linsolv','umfpack_reuse',deck],output/'native.log',deadline,16)
        verify(pins)
        if fingerprint(raw)!=sr['source_file_fingerprint']:raise ValueError('full reference RAW changed')
        rows,info=read_prefix(waveform,roles)
        if info['incomplete_final_sample_discarded'] or abs(rows[-1][0]-60e-9)>1e-18:raise ValueError('normal native completion without complete 60 ns output')
        result=frequency(rows,20,60)
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(waveform):sha(waveform)},native_exit_zero=True,
            all_saved_values_finite=True,measured_window_ns=[20,60],frequency=result,waveform=info,
            exterior_switching_qualified=False,receiver_loading_bounded=False,frequency_correlation_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='real_driver_DCO_diagnostic_complete',release_ready=False));print(json.dumps(result))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['plan','inventory','halo','model','native','snapshot','output']:p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--cpu',type=int,choices=range(16,32),required=True)
    a=p.parse_args();os.environ.update(OMP_NUM_THREADS='1',OMP_THREAD_LIMIT='1',OPENBLAS_NUM_THREADS='1')
    run(*(getattr(a,n).resolve() for n in ['plan','inventory','halo','model','native','snapshot','output']),a.cpu)
