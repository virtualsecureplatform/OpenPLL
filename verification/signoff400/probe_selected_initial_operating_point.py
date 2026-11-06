"""Test DC initialization with all exterior cuts from one recorded native state.

The one-nanosecond observation precedes reset release. No frequency, startup,
steady-state or boundary-switching qualification follows from this control.
"""
import argparse,json,math,os,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import identity,lease
from compiled_charge_v2 import execute
from check_selected_boundary_waveforms import bind
from audit_selected_dco_history_inputs import sources
from assess_selected_detector_prefix import read_prefix


def run(reference,plan,snapshot,output,cpu):
    os.sched_setaffinity(0,{cpu});output.mkdir(parents=True,exist_ok=False)
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    save(output/'status.json',dict(state='preparing_coherent_initial_DC_probe',release_ready=False))
    try:
        m=json.loads((reference/'manifest.json').read_text());p=json.loads(plan.read_text());s=json.loads(snapshot.read_text())
        verify(m['input_sha256']);verify(p['input_sha256']);verify(s['artifacts'])
        verify({k:v for k,v in s['input_sha256'].items() if not k.endswith('/profile.raw')})
        if m['input_sha256'].get(str(plan))!=sha(plan) or m['input_sha256'].get(str(snapshot))!=sha(snapshot):raise ValueError('same verified native partition and snapshot required')
        if m['operating_point']!=dict(corner='tt',supply_v=1.8,temperature_c=27):raise ValueError('original TT operating point required')
        vectors=[Path(k) for k in s['artifacts'] if k.endswith('/initial_voltage_vector.json')]
        if len(vectors)!=1:raise ValueError('unique recorded initial vector required')
        v=json.loads(vectors[0].read_text())
        if v['time_s']!=0 or len(v['values'])!=len(v['variable_names']) or any(not math.isfinite(x) for x in v['values']):raise ValueError('complete finite time-zero state required')
        nodes=set(p['required_non_supply_boundary_voltage_nodes']);b=bind(nodes,v['variable_names'])
        if not b['all_bound']:raise ValueError('all source cuts must bind to same recorded state')
        old=sources(reference/'sources.spice');rails={'VPWR','VPB','VGND','VNB'}
        if old.keys()!=nodes|rails:raise ValueError('source inventory differs from verified partition')
        source=output/'sources.spice'
        with source.open('x') as stream:
            for n,(name,value) in old.items():
                if n in nodes:value=format(v['values'][b['bindings'][n]['index']],'.17g')
                stream.write(f'{name} {n} 0 {value}\n')
        devices=output/'devices.spice';devices.write_bytes((reference/'devices.spice').read_bytes())
        deck=output/'control.spice';waveform=output/'control.raw'
        text=(reference/'control.spice').read_text()
        for name in ['sources.spice','devices.spice']:text=text.replace(str(reference/name),str(output/name))
        text=text.replace(str(reference/'control.raw'),str(waveform))
        if text.count('.tran 10p 60n 0 10p')!=1:raise ValueError('expected original transient protocol required')
        deck.write_text(text.replace('.tran 10p 60n 0 10p','.tran 10p 1n 0 10p'))
        binary=ROOT/'build/tools/xyce_umfpack_value_gather_001/Xyce'
        files=[Path(__file__).resolve(),Path(__file__).with_name('resources.py'),Path(__file__).with_name('compiled_charge_v2.py'),Path(__file__).with_name('check_selected_boundary_waveforms.py'),Path(__file__).with_name('audit_selected_dco_history_inputs.py'),Path(__file__).with_name('assess_selected_detector_prefix.py'),reference/'manifest.json',reference/'devices.spice',reference/'sources.spice',reference/'control.spice',plan,snapshot,vectors[0],source,devices,deck,binary]
        pins={str(f):sha(f) for f in files};verify(pins)
        roles=m['observed_roles']
        save(output/'manifest.json',dict(input_sha256=pins,CPU=cpu,MPI_ranks=1,memory_GiB=16,native_cap_s=900,observed_roles=roles,operating_point=m['operating_point'],all_exterior_sources_from_same_recorded_time_s=0,programming_inputs_static_target_400MHz=False,node_guesses_used=False,frequency_calibration=False,release_ready=False))
        deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+900
        save(output/'status.json',dict(state='coherent_initial_DC_native_running',release_ready=False))
        with lease(1,16,deadline):execute([binary,'-a','-linsolv','umfpack_reuse',deck],output/'native.log',deadline,16)
        verify(pins);rows,info=read_prefix(waveform,roles)
        if info['incomplete_final_sample_discarded'] or info['declared_samples']!=len(rows) or abs(rows[-1][0]-1e-9)>1e-18:raise ValueError('complete finite one-nanosecond output required')
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(waveform):sha(waveform)},native_exit_zero=True,DC_solve_completed=True,observation_end_ns=1,waveform=info,scope='DC initialization only; no reset release, target frequency or full initial-state equivalence established',release_ready=False))
        save(output/'status.json',dict(state='coherent_initial_DC_probe_complete',release_ready=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['reference','plan','snapshot','output']:p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--cpu',type=int,choices=range(16,32),required=True)
    a=p.parse_args();os.environ.update(OMP_NUM_THREADS='1',OMP_THREAD_LIMIT='1',OPENBLAS_NUM_THREADS='1')
    run(*(getattr(a,n).resolve() for n in ['reference','plan','snapshot','output']),a.cpu)
