"""Run the independent fine112 history holdout on the sparse-history settings.

Recorded programming history is applied at real inverter inputs until 170 ns.
Actual reset input history is replayed; other exterior nodes retain final DC.
The first reset/output physical-cell halo and all incident passives are kept.
Quiet exterior voltages and remaining omitted loads limit this to diagnosis.
"""
import argparse,json,os,re,time
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
from selected_dco_sparse_history_sources_v2 import prepare as prepare_history


def programming_sources(entries,coarse,fine):
    if type(coarse) is not int or type(fine) is not int or not 0<=coarse<=47 or not 8<=fine<=247:raise ValueError('supported static programming codes required')
    expected={f'DCO_THERM[{i}]' for i in range(255)}|{f'COARSETHERMAL_CODE[{i}]' for i in range(47)}
    if set(entries)!=expected:raise ValueError('complete physical programming driver inventory required')
    sources={}
    for port,entry in entries.items():
        index=int(port.split('[')[1][:-1])
        high=index<fine if port.startswith('DCO_THERM[') else index>=coarse
        node=entry['driver_input_node']
        if node in sources:raise ValueError('programming driver inputs unexpectedly alias')
        sources[node]=1.8 if high else 0.0
    return sources


def run(plan,inventory,halo,model,native,snapshot,output,cpu,history,coarse=20,fine=111,corner='tt',mpi_cpus=None):
    if (coarse,fine,corner)!=(20,112,'tt'):raise ValueError('independent history holdout supports TT coarse20 fine112 only')
    # Require actual full-native fine112 histories, never retarget fine111 sources.
    history_record=json.loads(history.read_text())
    verify({p:d for p,d in history_record['input_sha256'].items() if not p.endswith('/profile.raw')})
    history_manifests=[Path(p) for p in history_record['input_sha256'] if p.endswith('/manifest.json')]
    if len(history_manifests)!=1:raise ValueError('unique original history native manifest required')
    history_manifest=history_manifests[0]
    verify({str(history_manifest):history_record['input_sha256'][str(history_manifest)]})
    hm=json.loads(history_manifest.read_text());verify(hm['input_sha256'])
    if hm.get('startup_fine')!=fine or hm['input_sha256'].get(str(model))!=sha(model):raise ValueError('history code or physical model differs')
    if not any(p.endswith('/profile.raw') for p in history_record['input_sha256']):raise ValueError('actual source RAW binding required')
    if mpi_cpus:raise ValueError('serial control only until MPI benchmark completes')
    if corner not in ['tt','ff','ss','sf','fs']:raise ValueError('unsupported process corner')
    if mpi_cpus and (len(set(mpi_cpus))!=len(mpi_cpus) or not set(mpi_cpus)<=set(range(16,24))):raise ValueError('unique spare MPI CPUs 16..23 required')
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
        controls=programming_sources(iv['controls'],coarse,fine)
        reset=pv['prescribed_reset_driver_input']
        if len(controls)!=302 or set(controls)!=set(pv['prescribed_control_driver_input_nodes']) or not reset or reset in controls:raise ValueError('complete independent programming and reset input cuts required')
        if not (set(controls)|{reset})<=set(boundaries):raise ValueError('all prescribed voltages must be on the circuit boundary')
        outputs=[e['node'] for n in hv['signal_interfaces'].values() for e in n['inside'] if e['direction']=='OUTPUT']
        reset_pins=[e['node'] for n in hv['signal_interfaces'].values() for e in n['inside'] if e['direction']=='INPUT']
        if len(outputs)!=1 or len(reset_pins)!=1:raise ValueError('unique DCO output and reset pin required')
        roles=dict(oscillator=outputs[0],DCO_reset=reset_pins[0],reset_driver_input=reset)
        if not {outputs[0],reset_pins[0]}<=set(pv['private_unknown_nodes']):raise ValueError('DCO output and reset must remain circuit unknowns')
        devices=output/'devices.spice';export(model,pv,devices)
        history_sources,history_pins=prepare_history(history,iv['controls'],reset,output/'history_sources')
        if set(history_sources)!=set(controls)|{reset}:raise ValueError('history source inventory mismatch')
        from selected_native_clock_shapes import load
        for node, expected in controls.items():
            path=Path(re.fullmatch(r'PWL FILE "([^"]+)"',history_sources[node])[1])
            rows=load(path)
            if abs(rows[-1][1]-expected)>.01:raise ValueError('captured final programming levels differ from requested code')
        source=output/'sources.spice'
        with source.open('x') as f:
            for i,node in enumerate(boundaries):
                value=history_sources.get(node,format(quiet[node],'.17g'))
                f.write(f'Vcut{i} {node} 0 {value}\n')
            for i,(node,value) in enumerate([('VPWR',1.8),('VPB',1.8),('VGND',0),('VNB',0)]):f.write(f'Vrail{i} {node} 0 {value}\n')
        save(output/'exterior_final_voltages.json',quiet)
        deck=output/'control.spice';waveform=output/'control.raw'
        deck.write_text(f'''Conditional full-derived DCO with real programming drivers
.lib "/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae/sky130A/libs.tech/ngspice/sky130.lib.spice" {corner}
.include "{devices}"
.include "{source}"
.options parser model_binning=true
.options device temp=27
.options nonlin reltol=1e-5 abstol=1e-9
.options timeint reltol=1e-5 abstol=1e-9
.tran 10p 260n {{schedule(0,1n,100n,10p,112n,1n,175n,10p)}}
.print tran format=raw precision=17 file={waveform} {' '.join('v('+n+')' for n in roles.values())}
.end
''')
        binary=ROOT/'build/tools/xyce_umfpack_value_gather_001/Xyce'
        paths=[history_manifest,Path(__file__).with_name('selected_native_clock_shapes.py'),plan,inventory,halo,model,manifest,snapshot,devices,source,deck,output/'exterior_final_voltages.json',binary,Path(__file__).resolve(),Path(__file__).with_name('audit_selected_dco_final_bias.py'),Path(__file__).with_name('capture_selected_native_initial_snapshot.py'),Path(__file__).with_name('check_selected_boundary_waveforms.py'),Path(__file__).with_name('run_selected_detector_phase_probe_v5.py'),Path(__file__).with_name('assess_selected_detector_prefix.py'),Path(__file__).with_name('assess_selected_isolated_control.py'),Path(__file__).with_name('compiled_charge_v2.py')]
        if mpi_cpus:paths.extend([ROOT/'tools/xyce_umfpack/rank_exec.py',Path('/usr/bin/mpirun')])
        pins={str(p):sha(p) for p in paths};pins.update(history_pins);verify(pins)
        save(output/'manifest.json',dict(input_sha256=pins,CPU=cpu,MPI_CPUs=mpi_cpus,MPI_ranks=len(mpi_cpus) if mpi_cpus else 1,memory_GiB=24 if mpi_cpus else 8,native_cap_s=10800,maximum_programming_waveform_error_v=1e-3,maximum_reset_waveform_error_v=1e-6,timestep_schedule_ns=[[0,1],[100,.01],[112,1],[175,.01]],automatic_identical_retry=False,
            selected_primitives=len(pv['selected_primitives']),retained_passive_cards=len(pv['retained_passive_cards']),
            reference_raw_sha256=sr['input_sha256'][str(raw)],reference_raw_rehashed_this_run=False,
            reference_raw_file_fingerprint=sr['source_file_fingerprint'],observed_roles=roles,
            controls=dict(coarse=coarse,fine=fine,fine_inverse=True,actual_HS_INV2_inputs_driven=True),
            operating_point=dict(corner=corner,supply_v=1.8,temperature_c=27),quiet_exterior_snapshot_operating_point=dict(corner='tt',supply_v=1.8,temperature_c=27),reset='recorded actual CLKBUF4 input history',
            exterior_condition='recorded programming through 170 ns then held; recorded reset; other exterior nodes at full native final DC',remaining_omitted_primitive_load_count=len(pv['omitted_primitives_touching_private_nodes']),
            exterior_switching_qualified=False,receiver_loading_bounded=False,frequency_correlation_qualified=False,release_ready=False))
        deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+10800
        save(output/'status.json',dict(state='real_driver_DCO_native_running',release_ready=False))
        command=[binary,'-a','-linsolv','umfpack_reuse',deck]
        if mpi_cpus:command=[Path('/usr/bin/mpirun'),'--bind-to','none','-np',len(mpi_cpus),'/usr/bin/python3',ROOT/'tools/xyce_umfpack/rank_exec.py','--cpus',','.join(map(str,mpi_cpus)),'--',*command]
        with lease(len(mpi_cpus) if mpi_cpus else 1,24 if mpi_cpus else 8,deadline):execute(command,output/'native.log',deadline,12 if mpi_cpus else 8)
        verify(pins)
        if fingerprint(raw)!=sr['source_file_fingerprint']:raise ValueError('full reference RAW changed')
        rows,info=read_prefix(waveform,roles)
        if info['incomplete_final_sample_discarded'] or info['declared_samples']!=len(rows) or abs(rows[-1][0]-260e-9)>1e-18:raise ValueError('normal native completion without complete 260 ns output')
        result=frequency(rows,200,260)
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(waveform):sha(waveform)},native_exit_zero=True,
            all_saved_values_finite=True,operating_point=dict(corner=corner,supply_v=1.8,temperature_c=27),coarse=coarse,fine=fine,measured_window_ns=[200,260],frequency=result,waveform=info,
            exterior_switching_qualified=False,receiver_loading_bounded=False,frequency_correlation_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='real_driver_DCO_diagnostic_complete',release_ready=False));print(json.dumps(result))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['plan','inventory','halo','model','native','snapshot','output']:p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--history',type=Path,required=True)
    p.add_argument('--cpu',type=int,choices=range(16,32),required=True)
    p.add_argument('--coarse',type=int,default=20);p.add_argument('--fine',type=int,default=112);p.add_argument('--corner',choices=['tt','ff','ss','sf','fs'],default='tt');p.add_argument('--mpi-cpus')
    a=p.parse_args();os.environ.update(OMP_NUM_THREADS='1',OMP_THREAD_LIMIT='1',OPENBLAS_NUM_THREADS='1')
    run(*(getattr(a,n).resolve() for n in ['plan','inventory','halo','model','native','snapshot','output']),a.cpu,a.history.resolve(),a.coarse,a.fine,a.corner,[int(s) for s in a.mpi_cpus.split(',')] if a.mpi_cpus else None)
