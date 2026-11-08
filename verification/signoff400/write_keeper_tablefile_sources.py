"""Write literal TABLEFILE boundary sources, explicitly excluding the oscillator output."""
import argparse,json,math
from pathlib import Path
import numpy as np
from common_v3 import save,sha,verify

def write_sources(array,columns,destination):
    order=columns['ordered_physical_ports'];bindings=columns['bindings']
    if array.ndim!=2 or array.shape!=(columns['samples'],1+len(order)) or array.shape[0]<2:raise ValueError('complete array shape required')
    if len(set(order))!=len(order) or set(order)!=set(bindings):raise ValueError('unique complete column roles required')
    observed=[n for n in order if bindings[n]['role']=='observation_only']
    if observed!=['PLLOUT'] or bindings['PLLOUT']['role']!='observation_only':raise ValueError('one unforced observed PLLOUT required')
    if any(bindings[n]['role'] not in ['observation_only','externally_driven'] for n in order):raise ValueError('unknown port role')
    times=array[:,0]
    if not np.isfinite(times).all() or times[0]!=0 or not np.all(np.diff(times)>0):raise ValueError('finite increasing time from zero required')
    ports=[bindings[n]['conditional_formal_port'] for n in order]
    if len({n.lower() for n in ports})!=len(ports) or any(not n.replace('_','').isalnum() for n in ports):raise ValueError('unique safe port names required')
    stats=dict(driven_ports=0,observation_only_ports=['PLLOUT'],constant_waveforms=0,nonconstant_waveforms=0,input_driven_samples=0,emitted_PWL_points=0,lossy_compression_applied=False,PLLOUT_forced=False)
    table_dir=destination.parent/'tables';table_dir.mkdir(exist_ok=False)
    with destination.open('x') as stream:
        stream.write('* Sampled native boundary replay; PLLOUT is never driven.\n')
        for i,physical in enumerate(order):
            values=array[:,i+1]
            if not np.isfinite(values).all():raise ValueError('nonfinite saved boundary')
            if physical=='PLLOUT':continue
            if bindings[physical]['role']!='externally_driven':raise ValueError('unrecognized observation role')
            constant=bool(np.all(values==values[0]));indices=[0,len(times)-1] if constant else range(len(times))
            stats['constant_waveforms' if constant else 'nonconstant_waveforms']+=1;stats['input_driven_samples']+=len(times);stats['emitted_PWL_points']+=len(indices)
            data=table_dir/(str(stats['driven_ports'])+'.dat')
            with data.open('x') as target:
                for j in indices:target.write(format(float(times[j]),'.17g')+' '+format(float(values[j]),'.17g')+'\n')
            stream.write('Breplay'+str(stats['driven_ports'])+' '+bindings[physical]['conditional_formal_port']+' 0 V={TABLEFILE("'+str(data.resolve())+'")}\n')
            stats['driven_ports']+=1
    stats.update(source_representation='linear TABLEFILE with native knot breakpoints',downsampling_requested=False)
    return stats

def run(waveforms,output):
    receipt=waveforms/'assessment.json';a=json.loads(receipt.read_text());verify(a['input_sha256']);verify(a['artifacts'])
    if not a['completed_boundary_waveforms_available'] or not a['all_saved_native_values_finite'] or not a['PLLOUT_is_observation_only']:raise ValueError('checked completed full-reference extraction required')
    columns_file=waveforms/'columns.json';array_file=waveforms/'boundary.npy';pins={str(p):sha(p) for p in [receipt,columns_file,array_file,Path(__file__).resolve()]}
    columns=json.loads(columns_file.read_text());array=np.load(array_file,mmap_mode='r');output.mkdir(parents=True,exist_ok=False);sources=output/'external_sources.spice'
    try:
        stats=write_sources(array,columns,sources);verify(pins);save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in [sources,*sorted((output/'tables').glob('*.dat'))]},**stats,sampled_PWL_environment_only=True,replay_executed=False,environment_validated=False,model_qualified=False,release_ready=False))
    except BaseException as e:
        save(output/'status.json',dict(state='source_generation_failed',reason=repr(e),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['waveforms','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve() for n in ['waveforms','output']))
