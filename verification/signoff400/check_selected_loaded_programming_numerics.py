"""Repeat the worst sampled loaded-path case with tighter integration settings."""
import argparse,json,os,time
from pathlib import Path
from common_v3 import save,sha,verify
from resources import identity,lease
from compiled_charge_v2 import execute
from assess_selected_detector_prefix import read_prefix
from run_selected_programming_loaded_screen import slew


def run(campaign,plan,output):
    os.sched_setaffinity(0,{27});output.mkdir(parents=True,exist_ok=False)
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    save(output/'status.json',dict(state='preparing_loaded_path_numerical_check',release_ready=False))
    try:
        receipt=campaign/'assessment.json';a=json.loads(receipt.read_text());verify(a['input_sha256']);verify(a['artifacts'])
        if not a['all_24_native_cases_completed'] or len(a['results'])!=24:raise ValueError('complete original native campaign required')
        corner_rows=[r for r in a['results']if r['corner']=='sf']
        worst=max(corner_rows,key=lambda r:max(r['measured_slew']['logic_output'].values()))
        name=f'sf_{worst["arc"]}_{worst["receiver_phase"][0]}{worst["receiver_phase"][1]}'
        source=campaign/name/'profile.spice'
        if a['input_sha256'].get(str(source))!=sha(source):raise ValueError('original case deck not pinned')
        original_raw=campaign/name/'profile.raw'
        if a['artifacts'].get(str(original_raw))!=sha(original_raw):raise ValueError('original waveform not pinned')
        p=json.loads(plan.read_text());verify(p['input_sha256']);roles=p['observed_roles']
        if p['role']!='DCO_THERM[226]':raise ValueError('same identified loaded path required')
        rows,info=read_prefix(original_raw,roles)
        measured={role:slew(rows,col+1)for col,role in enumerate(roles)}
        if measured!=worst['measured_slew']:raise ValueError('original native slew not reproduced')
        text=source.read_text();old='.tran 2p 20n 0 2p'
        if text.splitlines().count(old)!=1:raise ValueError('original 2 ps protocol required')
        for kind in ('nonlin','timeint'):
            token=f'.options {kind} reltol=1e-5 abstol=1e-9'
            if text.count(token)!=1:raise ValueError('explicit original tolerance required')
            text=text.replace(token,f'.options {kind} reltol=1e-6 abstol=1e-10')
        raw=output/'profile.raw';deck=output/'profile.spice'
        text=text.replace(old,'.tran 1p 20n 0 1p').replace(str(original_raw),str(raw));deck.write_text(text)
        binaries=[Path(p)for p in a['input_sha256']if p.endswith('/Xyce')]
        if len(binaries)!=1:raise ValueError('unique actual native executable required')
        binary=binaries[0]
        files=[receipt,source,original_raw,plan,deck,binary,Path(__file__).resolve()]
        files += [Path(__file__).with_name(n)for n in ('common_v3.py','resources.py','compiled_charge_v2.py','assess_selected_detector_prefix.py','run_selected_programming_loaded_screen.py')]
        pins={str(p):sha(p)for p in files};verify(pins)
        save(output/'manifest.json',dict(input_sha256=pins,CPU=27,MPI_ranks=1,memory_GiB=4,case=name,maximum_step_ps=1,reltol=1e-6,abstol=1e-10,release_ready=False))
        deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+600
        save(output/'status.json',dict(state='loaded_path_numerical_native_running',release_ready=False))
        with lease(1,4,deadline):execute([binary,'-a','-linsolv','umfpack_reuse',deck],output/'native.log',deadline,4)
        verify(pins);rows,info=read_prefix(raw,roles)
        if info['incomplete_final_sample_discarded'] or abs(rows[-1][0]-20e-9)>1e-18:raise ValueError('complete tighter native waveform required')
        tighter={role:slew(rows,col+1)for col,role in enumerate(roles)}
        differences={role:{edge:tighter[role][edge]-measured[role][edge]for edge in ('rise_ps','fall_ps')}for role in roles}
        maximum=max(abs(v)for d in differences.values()for v in d.values())
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(raw):sha(raw),str(output/'native.log'):sha(output/'native.log')},
            case=name,original_slew_ps=measured,tighter_slew_ps=tighter,slew_difference_ps=differences,maximum_absolute_slew_difference_ps=maximum,
            within_original_2ps_step_resolution=maximum<=2,baseline_maximum_step_ps=2,tighter_maximum_step_ps=1,
            numerical_case_only=True,input_slew_range_qualified=False,exterior_coupling_qualified=False,loaded_path_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='loaded_path_numerical_check_assessed',release_ready=False));print(json.dumps(differences))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('campaign','plan','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve()for n in ('campaign','plan','output')))
