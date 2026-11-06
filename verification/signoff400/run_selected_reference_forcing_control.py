"""Replace only two held REFCLK boundary voltages with recorded native curves.

This is a conditional forcing-sensitivity control. The recorded voltages belong
to a particular full-native trajectory; replay does not establish a universally
valid exterior impedance or a closed-loop frequency/phase uncertainty bound.
"""
import argparse,json,os,re,shutil,time,math
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import identity,lease
from compiled_charge_v2 import execute
from capture_selected_native_initial_snapshot import fingerprint
from selected_native_clock_shapes import load,shift_window
from bounded_clock_sources import prepare as bounded
from audit_selected_dco_history_inputs import sources
from assess_selected_detector_prefix import read_prefix
from assess_selected_isolated_control import frequency


def run(reference,capture,proof,output,cpu,start_ns=200,prepare_only=False):
    if cpu not in range(16,32) or not math.isfinite(start_ns) or not 180<=start_ns<=200:raise ValueError('covered steady-state window and spare physical CPU required')
    os.sched_setaffinity(0,{cpu});output.mkdir(parents=True,exist_ok=False)
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    save(output/'status.json',dict(state='preparing_reference_forcing_control',release_ready=False))
    try:
        m=json.loads((reference/'manifest.json').read_text());verify(m['input_sha256'])
        if m.get('operating_point')!=dict(corner='tt',temperature_c=27,supply_v=1.8):raise ValueError('matching TT diagnostic baseline required')
        if m.get('controls',{}).get('coarse')!=20 or m['controls'].get('fine')!=111:raise ValueError('recorded forcing is scoped to full TT coarse20 fine111')
        c=json.loads((capture/'assessment.json').read_text());raws={path:digest for path,digest in c['input_sha256'].items() if path.endswith('/profile.raw')}
        if len(raws)!=1:raise ValueError('unique verified original RAW identity required')
        raw,digest=next(iter(raws.items()))
        if digest!=m['reference_raw_sha256'] or fingerprint(Path(raw))!=m['reference_raw_file_fingerprint']:raise ValueError('capture and baseline must share the immutable native RAW')
        verify({path:digest for path,digest in c['input_sha256'].items() if path not in raws});verify(c['artifacts'])
        p=json.loads(proof.read_text());verify(p['input_sha256'])
        nodes={r['node'] for r in p['switching_cuts_above_0p1V']}
        if len(nodes)!=2 or any(r['resistively_connected_top_ports']!=['REFCLK'] for r in p['switching_cuts_above_0p1V']):raise ValueError('exact two REFCLK resistive boundaries required')
        items=c['clock_driver_waveforms']
        if {r['node'] for r in items.values()}!=nodes or not c['exact_saved_knots_preserved'] or not c['source_complete_and_all_values_finite']:raise ValueError('complete native REFCLK boundary observations required')
        src=sources(reference/'sources.spice')
        if not nodes<=src.keys():raise ValueError('recorded boundaries are absent from baseline')
        original={n:src[n][1] for n in nodes}
        if any(not math.isfinite(float(v)) for v in original.values()):raise ValueError('original reference boundaries must be constant voltages')
        paths=[reference/'manifest.json',reference/'devices.spice',reference/'sources.spice',reference/'control.spice',capture/'assessment.json',proof,Path(__file__).resolve(),Path(__file__).with_name('selected_native_clock_shapes.py'),Path(__file__).with_name('bounded_clock_sources.py'),Path(__file__).with_name('audit_selected_dco_history_inputs.py'),Path(__file__).with_name('assess_selected_detector_prefix.py'),Path(__file__).with_name('assess_selected_isolated_control.py'),Path(__file__).with_name('compiled_charge_v2.py'),Path(__file__).with_name('capture_selected_native_initial_snapshot.py')]
        pins={str(path):sha(path) for path in paths};curves={};details={}
        for role,item in items.items():
            path=Path(item['file']);pins[str(path)]=sha(path);rows=shift_window(load(path),start_ns*1e-9,60e-9)
            dest=output/(role+'_recorded.pwl')
            with dest.open('x') as stream:
                for t,v in rows:stream.write(f'{t:.17g} {v:.17g}\n')
            curves[role]=dest;details[role]=dict(node=item['node'],source=str(path),source_window_ns=[start_ns,start_ns+60],time_translation_s=start_ns*1e-9,knots=len(rows),time_warp_applied=False,extrapolation_applied=False)
        replacements,curve_pins=bounded(curves,output/'bounded_reference_sources',1e-6);pins.update(curve_pins)
        by_node={items[role]['node']:replacements[role] for role in items}
        target=output/'sources.spice';count=0
        with target.open('x') as stream:
            for line in (reference/'sources.spice').open():
                f=line.split(maxsplit=3)
                if len(f)==4 and f[1] in by_node:
                    line=f'{f[0]} {f[1]} {f[2]} {by_node[f[1]]}\n';count+=1
                stream.write(line)
        if count!=2:raise ValueError('exactly two source cards must change')
        old,new=src,sources(target)
        if old.keys()!=new.keys() or {n for n in old if old[n][1]!=new[n][1]}!=nodes:raise ValueError('only the two reference source values may change')
        devices=output/'devices.spice';shutil.copyfile(reference/'devices.spice',devices)
        if sha(devices)!=m['input_sha256'][str(reference/'devices.spice')]:raise ValueError('physical circuit changed')
        deck=output/'control.spice';text=(reference/'control.spice').read_text()
        for name in ['devices.spice','sources.spice','control.raw']:
            if text.count(str(reference/name))!=1:raise ValueError('one original circuit/output path required')
            text=text.replace(str(reference/name),str(output/name))
        deck.write_text(text)
        binaries=[Path(path) for path in m['input_sha256'] if path.endswith('/Xyce')]
        if len(binaries)!=1:raise ValueError('one pinned native executable required')
        binary=binaries[0]
        for path in [target,devices,deck,binary]:pins[str(path)]=sha(path)
        verify(pins)
        save(output/'manifest.json',dict(input_sha256=pins,reference=str(reference),operating_point=m['operating_point'],controls=m['controls'],observed_roles=m['observed_roles'],
            recorded_reference_sources=details,original_constant_reference_voltages=original,changed_voltage_sources=sorted(nodes),physical_device_and_passive_file_identical=True,
            source_voltage_approximation_bound_relative_recorded_PWL_V=1e-6,source_trajectory='recorded full TT fine111, cropped and translated; not a universal exterior model',
            CPU=cpu,memory_GiB=16,native_cap_s=10800,automatic_identical_retry=False,frequency_correlation_qualified=False,release_ready=False))
        if prepare_only:
            save(output/'status.json',dict(state='prepared_without_native_execution',release_ready=False));return
        deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+10800
        save(output/'status.json',dict(state='reference_forcing_native_running',release_ready=False))
        with lease(1,16,deadline):execute([binary,'-a','-linsolv','umfpack_reuse',deck],output/'native.log',deadline,16)
        verify(pins);rows,info=read_prefix(output/'control.raw',m['observed_roles'])
        if info['declared_samples']!=len(rows) or info['incomplete_final_sample_discarded'] or abs(rows[-1][0]-60e-9)>1e-18:raise ValueError('complete finite 60 ns observations required')
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(output/'control.raw'):sha(output/'control.raw')},native_exit_zero=True,all_saved_values_finite=True,
            frequency=frequency(rows,20,60),measured_window_ns=[20,60],waveform=info,frequency_error_causality_generalized=False,physical_models_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='reference_forcing_control_completed',release_ready=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ['reference','capture','proof','output']:p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--cpu',type=int,required=True,choices=range(16,32));p.add_argument('--start-ns',type=float,default=200);p.add_argument('--prepare-only',action='store_true')
    a=p.parse_args();run(*(getattr(a,n).resolve() for n in ['reference','capture','proof','output']),a.cpu,a.start_ns,a.prepare_only)
