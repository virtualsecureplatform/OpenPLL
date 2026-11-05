"""Conditional active detector diagnostic; never a qualified interface model.

Exterior active terminals are held at the full native initial sample. Clock
and reset cuts are explicit. Omitted loads remain reported qualification gaps.
"""
import argparse,json,math,os,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import identity,lease
from compiled_charge_v2 import execute
from check_selected_boundary_waveforms import bind


def first_sample(raw):
    names=[];declared=None
    with raw.open() as stream:
        for line in stream:
            if line.startswith('No. Variables:'):declared=int(line.split(':',1)[1])
            if line.strip()=='Variables:':break
        for line in stream:
            if line.strip()=='Values:':break
            index,name,_=line.split()
            if int(index)!=len(names):raise ValueError('invalid RAW variable ordering')
            names.append(name)
        if len(names)!=declared or names[0].lower()!='time':raise ValueError('incomplete RAW header')
        fields=next(stream).split()
        if len(fields)!=2 or int(fields[0])!=0 or float(fields[1])!=0:raise ValueError('initial native sample required')
        values=[0.0]+[float(next(stream)) for _ in range(declared-1)]
    if not all(math.isfinite(v) for v in values):raise ValueError('nonfinite initial native sample')
    return names,values


def pulse(phase_ns,rise_ps,period_ns):
    # Phase names the first 50% crossing, independent of slew.
    if not all(math.isfinite(v) for v in [phase_ns,rise_ps,period_ns]) or rise_ps<=0 or period_ns<=0:raise ValueError('finite positive timing required')
    delay=20+phase_ns-rise_ps/2000
    width=period_ns/2-rise_ps/1000
    if delay<0 or width<=0:raise ValueError('invalid pulse timing')
    return f'PULSE(0 1.8 {delay:.12g}n {rise_ps:.12g}p {rise_ps:.12g}p {width:.12g}n {period_ns:.12g}n)'


def export(model,plan,destination):
    selected=set(plan['selected_primitives']);passives=set(plan['retained_passive_cards'])
    retained=selected|passives
    seen=set();inside=False;found=False
    with model.open() as src,destination.open('x') as out:
        for line in src:
            f=line.split()
            if f[:2]==['.subckt','IntegerPLL_400MHz_PrototypeTop']:
                if found:raise ValueError('duplicate native top')
                found=inside=True;continue
            if inside and f and f[0].lower()=='.ends':inside=False;continue
            if not inside:out.write(line);continue
            if f and f[0] in retained:out.write(line);seen.add(f[0])
    if not found or seen!=retained:raise ValueError('incomplete selected device/passive export')


def reuse_snapshot(snapshot_probe,physical_paths,raw,boundaries):
    state=json.loads((snapshot_probe/'status.json').read_text())['state']
    if state!='conditional_detector_probe_completed_assessment_pending':raise ValueError('completed reference probe required for snapshot reuse')
    reference_manifest=snapshot_probe/'manifest.json';reference_assessment=snapshot_probe/'assessment.json'
    rm=json.loads(reference_manifest.read_text());ra=json.loads(reference_assessment.read_text())
    if not ra.get('native_exit_zero') or ra['input_sha256']!=rm['input_sha256']:raise ValueError('reference completion provenance mismatch')
    for path in physical_paths:
        if rm['input_sha256'].get(str(path))!=sha(path):raise ValueError('snapshot physical/stimulus identity mismatch')
    snapshot_path=snapshot_probe/'exterior_initial_voltages.json'
    if rm['input_sha256'].get(str(snapshot_path))!=sha(snapshot_path):raise ValueError('snapshot artifact changed')
    snapshot=json.loads(snapshot_path.read_text())
    if set(snapshot)!=set(boundaries) or not all(isinstance(v,(int,float)) and math.isfinite(v) for v in snapshot.values()):raise ValueError('complete finite exterior snapshot required')
    reference_raw_sha=rm['input_sha256'].get(str(raw))
    if not reference_raw_sha:raise ValueError('reference RAW identity missing')
    snapshot_pins={str(p):sha(p) for p in [reference_manifest,reference_assessment,snapshot_path]}
    return snapshot,snapshot_pins,reference_raw_sha


def reuse_initial_vector(folder,native_manifest,raw,boundaries):
    receipt=folder/'assessment.json';a=json.loads(receipt.read_text())
    if json.loads((folder/'status.json').read_text())['state']!='full_initial_voltage_snapshot_captured':raise ValueError('completed initial-vector capture required')
    verify(a['artifacts'])
    verify({p:d for p,d in a['input_sha256'].items() if p!=str(raw)})
    if a['input_sha256'].get(str(native_manifest))!=sha(native_manifest):raise ValueError('initial-vector native identity mismatch')
    paths=[Path(p) for p in a['artifacts'] if p.endswith('/initial_voltage_vector.json')]
    if len(paths)!=1:raise ValueError('one full initial voltage vector required')
    v=json.loads(paths[0].read_text());names=v['variable_names'];values=v['values']
    if v['time_s']!=0 or len(names)!=len(values) or not all(isinstance(x,(int,float)) and math.isfinite(x) for x in values):raise ValueError('invalid finite initial vector')
    binding=bind(boundaries,names)
    if not binding['all_bound']:raise ValueError('expanded boundary is not covered by native initial vector')
    digest=a['input_sha256'].get(str(raw))
    if not digest:raise ValueError('source RAW provenance missing')
    return ({n:values[binding['bindings'][n]['index']] for n in boundaries},
            {str(p):sha(p) for p in [receipt,folder/'status.json',paths[0]]},digest)


def run(plan_path,stimuli_path,model,native,output,phase_ns,snapshot_probe=None,detector_ports=None,cpu=26,initial_snapshot=None):
    if cpu not in range(16,32):raise ValueError('detector diagnostic requires a spare physical CPU 16..31')
    os.sched_setaffinity(0,{cpu})
    output.mkdir(parents=True,exist_ok=False)
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    save(output/'status.json',dict(state='preparing_conditional_detector_phase_probe',release_ready=False))
    try:
        plan=json.loads(plan_path.read_text());sv=json.loads(stimuli_path.read_text())
        verify(plan['input_sha256']);verify(sv['input_sha256'])
        if plan['input_sha256'].get(str(stimuli_path))!=sha(stimuli_path) or plan['input_sha256'].get(str(model))!=sha(model):raise ValueError('partition stimulus/model identity mismatch')
        manifest=native/'manifest.json'
        if json.loads(manifest.read_text())['input_sha256'].get(str(model))!=sha(model):raise ValueError('native reference model mismatch')
        raw=native/'profile.raw'
        boundaries=plan['required_non_supply_boundary_voltage_nodes']
        snapshot_pins={};reference_raw_sha=None
        if initial_snapshot is not None:
            if snapshot_probe is not None:raise ValueError('choose one snapshot source')
            snapshot,snapshot_pins,reference_raw_sha=reuse_initial_vector(initial_snapshot,manifest,raw,boundaries)
        elif snapshot_probe is None:
            names,values=first_sample(raw)
            binding=bind(boundaries,names)
            if not binding['all_bound']:raise ValueError('every exterior voltage must have a native initial sample')
            snapshot={n:values[binding['bindings'][n]['index']] for n in boundaries}
        else:
            snapshot,snapshot_pins,reference_raw_sha=reuse_snapshot(snapshot_probe,[plan_path,stimuli_path,model,manifest],raw,boundaries)
        drives=sv['prescribed_voltage_roles'];observed=dict(sv['observed_unknown_roles'])
        if detector_ports is not None:
            pv=json.loads(detector_ports.read_text());verify(pv['input_sha256'])
            if sv['input_sha256'].get(str(detector_ports))!=sha(detector_ports):raise ValueError('detector measurement port identity mismatch')
            observed.update({role+'_pin':pv['ports'][port]['detector_wire_endpoint'] for role,port in [('reference','REF'),('feedback','CLKDIVR'),('detector_reset','RESET_N')]})
        if set(drives.values())&set(observed.values()):raise ValueError('output clamping forbidden')
        if not set(observed.values())<=set(plan['private_unknown_nodes']):raise ValueError('observed outputs must be circuit unknowns')
        if not set(drives.values())<=set(boundaries):raise ValueError('stimulus cuts must be prescribed boundary nodes')
        pins={str(p):sha(p) for p in [plan_path,stimuli_path,model,manifest,Path(__file__).resolve(),Path(__file__).with_name('check_selected_boundary_waveforms.py'),Path(__file__).with_name('compiled_charge_v2.py')]}
        pins.update(snapshot_pins)
        if detector_ports is not None:pins[str(detector_ports)]=sha(detector_ports)
        if snapshot_probe is None and initial_snapshot is None:pins[str(raw)]=sha(raw)
        binary=ROOT/'build/tools/xyce_umfpack_value_gather_001/Xyce';pins[str(binary)]=sha(binary)
        devices=output/'devices.spice';export(model,plan,devices)
        save(output/'exterior_initial_voltages.json',snapshot)
        source=output/'sources.spice'
        waveforms=dict(reference=pulse(0,100,40),feedback=pulse(phase_ns,600,40),
                       synchronizer_clock=pulse(-10,100,2.5))
        for role in ['detector_reset_n','event_reset_n','synchronizer_reset_n']:
            waveforms[role]='PWL(0 0 5n 0 5.2n 1.8 80n 1.8)'
        inverse={node:role for role,node in drives.items()}
        with source.open('x') as stream:
            for i,node in enumerate(boundaries):
                waveform=waveforms[inverse[node]] if node in inverse else format(snapshot[node],'.17g')
                stream.write(f'Vcut{i} {node} 0 {waveform}\n')
            for i,(node,value) in enumerate([('VPWR',1.8),('VPB',1.8),('VGND',0),('VNB',0)]):stream.write(f'Vrail{i} {node} 0 {value}\n')
        deck=output/'probe.spice';waveform=output/'probe.raw'
        outputs=list(dict.fromkeys([*observed.values(),*drives.values()]))
        deck.write_text(f'''Conditional active detector diagnostic; exterior native initial voltages held
.lib "/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae/sky130A/libs.tech/ngspice/sky130.lib.spice" tt
.include "{devices}"
.include "{source}"
.options parser model_binning=true
.options device temp=27
.options nonlin reltol=1e-5 abstol=1e-9
.options timeint reltol=1e-5 abstol=1e-9
.tran 10p 80n 0 10p
.print tran format=raw file={waveform} {' '.join('v('+n+')' for n in outputs)}
.end
''')
        pins.update({str(p):sha(p) for p in [devices,source,deck,output/'exterior_initial_voltages.json']})
        save(output/'manifest.json',dict(input_sha256=pins,phase_50_percent_crossing_offset_ns=phase_ns,
            reference_snapshot_probe=str(snapshot_probe) if snapshot_probe else None,
            reference_raw_sha256=reference_raw_sha or pins[str(raw)],
            reference_raw_rehashed_this_run=snapshot_probe is None and initial_snapshot is None,
            reference_initial_vector_snapshot=str(initial_snapshot) if initial_snapshot else None,
            native_cap_s=1800,CPU=cpu,memory_GiB=8,automatic_identical_retry=False,
            unqualified_waveform_full_ramps_ps=dict(reference=100,feedback=600,synchronizer_clock=100),
            exterior_condition='full native initial voltages held constant',
            omitted_primitive_loads=plan['omitted_primitives_touching_private_nodes'],
            observed_roles=observed,diagnostic=True,release_ready=False))
        deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+1800
        save(output/'status.json',dict(state='conditional_detector_native_running',release_ready=False))
        with lease(1,8,deadline):execute([binary,'-a','-linsolv','umfpack_reuse',deck],output/'native.log',deadline,8)
        verify(pins)
        if not waveform.exists():raise ValueError('native waveform missing')
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(waveform):sha(waveform)},
            native_exit_zero=True,active_phase_response_assessed=False,receiver_loading_bounded=False,
            exterior_condition_validated=False,physical_models_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='conditional_detector_probe_completed_assessment_pending',release_ready=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['plan','stimuli','model','native','output']:p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--phase-ns',type=float,required=True)
    p.add_argument('--cpu',type=int,required=True,choices=range(16,32))
    p.add_argument('--snapshot-probe',type=Path)
    p.add_argument('--initial-snapshot',type=Path)
    p.add_argument('--detector-ports',type=Path,required=True)
    a=p.parse_args();os.sched_setaffinity(0,{a.cpu});os.environ.update(OMP_NUM_THREADS='1',OMP_THREAD_LIMIT='1',OPENBLAS_NUM_THREADS='1')
    run(*(getattr(a,n).resolve() for n in ['plan','stimuli','model','native','output']),a.phase_ns,a.snapshot_probe.resolve() if a.snapshot_probe else None,a.detector_ports.resolve(),a.cpu,a.initial_snapshot.resolve() if a.initial_snapshot else None)
