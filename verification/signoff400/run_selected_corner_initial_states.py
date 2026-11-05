"""Capture full-circuit corner initial states after the original TT calibration.

Run one full circuit at a time, for 1 ps with reset asserted. Preserve native
DC solutions rather than transplanting TT exterior biases into another corner.
These snapshots do not characterize tuning, tracking, or device uncertainty.
"""
import argparse,json,os,re,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import identity,lease
from compiled_charge_v2 import execute
from assess_selected_detector_prefix import read_prefix


def deck_text(text,base,output,corner):
    if corner not in ['ff','ss','sf','fs']:raise ValueError('non-TT process corner required')
    libs=re.findall(r'^\.lib (.+) tt$',text,re.MULTILINE)
    if len(libs)!=1:raise ValueError('one TT native library card required')
    if text.splitlines().count('.tran 10p 260n 0 10p')!=1:raise ValueError('full baseline horizon required')
    if text.count(str(base/'profile.raw'))!=1:raise ValueError('one baseline RAW destination required')
    return re.sub(r'^\.lib (.+) tt$',lambda m:'.lib '+m[1]+' '+corner,text,flags=re.MULTILINE).replace(
        '.tran 10p 260n 0 10p','.tran 1p 1p 0 1p').replace(str(base/'profile.raw'),str(output/'profile.raw'))


def read_states(raw):
    names=[];variables=None
    with raw.open() as f:
        for line in f:
            if line.startswith('No. Variables:'):variables=int(line.split(':',1)[1])
            if line.strip()=='Variables:':break
        for line in f:
            if line.strip()=='Values:':break
            index,name,_=line.split()
            if int(index)!=len(names):raise ValueError('ordered native variable inventory required')
            names.append(name)
    if len(names)!=variables or not names or names[0].lower()!='time':raise ValueError('complete native variable inventory required')
    if any(not name.lower().startswith('v(') or not name.endswith(')') for name in names[1:]):raise ValueError('only native voltage observations required')
    rows,info=read_prefix(raw,{name:name[2:-1] for name in names[1:]})
    if info['declared_samples']!=len(rows) or info['incomplete_final_sample_discarded'] or abs(rows[-1][0]-1e-12)>1e-21:
        raise ValueError('normal complete 1 ps native waveform required')
    return dict(time_s=0.0,variable_names=names[1:],voltage_values=rows[0][1:]),info


def full_workers():
    result=[]
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit():continue
        try:
            args=(proc/'cmdline').read_bytes().split(b'\0')
            if not args or not args[0].endswith(b'/Xyce'):continue
            for arg in args[1:]:
                if not arg.endswith(b'/profile.spice'):continue
                manifest=Path(os.fsdecode(arg)).parent/'manifest.json'
                if manifest.exists() and json.loads(manifest.read_text()).get('MPI_ranks')==16:
                    if identity(int(proc.name)) is not None:result.append(int(proc.name))
        except (FileNotFoundError,ProcessLookupError,PermissionError):continue
    return result


def run(advance,base,image,output):
    libraries=re.findall(r'^\.lib "([^"]+)" tt$',(base/'profile.spice').read_text(),re.MULTILINE)
    if len(libraries)!=1 or not Path(libraries[0]).is_file():raise EnvironmentError('run this queue inside the pinned release container with its PDK')
    output.mkdir(parents=True,exist_ok=False)
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    owner=json.loads((advance/'owner.json').read_text())
    binary=ROOT/'build/tools/xyce_umfpack_value_gather_001/Xyce'
    helper=ROOT/'tools/xyce_umfpack/rank_exec.py'
    bm=json.loads((base/'manifest.json').read_text())
    files=[base/'manifest.json',base/'profile.spice',Path(__file__).resolve(),
           Path(__file__).with_name('assess_selected_detector_prefix.py'),
           Path(__file__).with_name('check_selected_boundary_waveforms.py'),binary,helper,image]
    if bm['input_sha256'].get(str(base/'profile.spice'))!=sha(base/'profile.spice'):raise ValueError('pinned full-circuit baseline required')
    pins={str(p):sha(p) for p in files};pins.update({p:d for p,d in bm['input_sha256'].items() if p.endswith('/model.spice')})
    verify(pins)
    save(output/'inputs.json',dict(input_sha256=pins,advance_owner=owner,corners=['ff','ss','sf','fs'],
        max_large_cases=1,reset_state_only=True,automatic_identical_retry=False,release_ready=False))
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+172800
    records=[]
    try:
        while True:
            state=json.loads((advance/'status.json').read_text())['state']
            if state=='calibration_attached_next_measurement_requested':break
            if state=='stopped_without_qualification':raise RuntimeError('original calibration advancement failed')
            if identity(owner['pid'])!=owner['birth']:raise RuntimeError('advancement owner exited without completion')
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('calibration observation deadline; original job unchanged')
            save(output/'status.json',dict(state='waiting_for_original_calibration_assessment',release_ready=False));time.sleep(10)
        receipt=advance/'assessment.json';a=json.loads(receipt.read_text());verify(a['input_sha256']);verify(a['artifacts'])
        pins[str(receipt)]=sha(receipt)
        for corner in ['ff','ss','sf','fs']:
            verify(pins)
            while full_workers():
                if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('another full-circuit native worker remains live')
                save(output/'status.json',dict(state='waiting_for_exclusive_full_native_slot',corner=corner,release_ready=False));time.sleep(10)
            folder=output/corner;folder.mkdir();deck=folder/'profile.spice'
            deck.write_text(deck_text((base/'profile.spice').read_text(),base,folder,corner))
            local=dict(pins,**{str(deck):sha(deck)})
            save(folder/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
            save(folder/'manifest.json',dict(input_sha256=local,MPI_ranks=16,CPUs=list(range(16)),memory_GiB=64,
                 corner=corner,temperature_c=27,supply_v=1.8,native_cap_s=3600,reset_state_only=True,release_ready=False))
            native_deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+3600
            save(output/'status.json',dict(state='corner_reset_state_native_running',corner=corner,release_ready=False))
            command=['/usr/bin/mpirun','--bind-to','none',
                '-np','16','/usr/bin/python3',helper,'--cpus',','.join(map(str,range(16))),'--',binary,'-a','-linsolv','umfpack_reuse',deck]
            with lease(16,64,native_deadline):execute(command,folder/'native.log',native_deadline,48)
            verify(local)
            vector,info=read_states(folder/'profile.raw');save(folder/'initial_voltage_vector.json',vector)
            save(folder/'assessment.json',dict(input_sha256=local,artifacts={str(p):sha(p) for p in [folder/'profile.raw',folder/'initial_voltage_vector.json']},
                corner=corner,temperature_c=27,supply_v=1.8,waveform=info,all_saved_values_finite=True,reset_state_only=True,
                native_exit_zero=True,tuning_qualified=False,physical_models_qualified=False,release_ready=False))
            records.append(dict(corner=corner,assessment=str(folder/'assessment.json'),sha256=sha(folder/'assessment.json')))
        verify(pins)
        save(output/'assessment.json',dict(input_sha256=pins,records=records,reset_state_only=True,
             all_process_corner_initial_states_captured=True,tuning_qualified=False,physical_models_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='corner_reset_state_snapshots_captured',release_ready=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    for name in ['advance','base','image','output']:parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();os.environ.update(OMP_NUM_THREADS='1',OMP_THREAD_LIMIT='1',OPENBLAS_NUM_THREADS='1')
    run(*(getattr(args,name).resolve() for name in ['advance','base','image','output']))
