"""Benchmark an existing completed DCO circuit with a new MPI rank count.

Only the RAW destination changes in the deck. Preserve all physics/tolerances,
compare all saved edges and the measured frequency, and never replace or retry
the original native run. MPI agreement is not a convergence qualification.
"""
import argparse,json,os,re,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import identity,lease
from compiled_charge_v2 import execute
from assess_selected_detector_prefix import read_prefix
from assess_selected_detector_phase_probe_v2 import transitions
from assess_selected_isolated_control import frequency


def rebind_output(text,path):
    lines=[];count=0
    for line in text.splitlines():
        if line.lower().startswith('.print '):line,n=re.subn(r'\bfile=\S+',lambda m:'file='+str(path),line,flags=re.I);count+=n
        lines.append(line)
    if count!=1:raise ValueError('exactly one RAW output destination required')
    return '\n'.join(lines)+'\n'


def elapsed(log):
    values=re.findall(r'Total Elapsed Run Time:\s+([0-9.]+) seconds',log.read_text())
    if not values:raise ValueError('normal native elapsed timing summary required')
    return max(map(float,values))


def run(reference,output,cpus):
    if not cpus or len(set(cpus))!=len(cpus) or not set(cpus)<=set(range(16,24)):raise ValueError('unique spare physical CPUs 16..23 required')
    output.mkdir(parents=True,exist_ok=False);save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    save(output/'status.json',dict(state='preparing_DCO_MPI_control',release_ready=False))
    try:
        if json.loads((reference/'status.json').read_text())['state']!='real_driver_DCO_diagnostic_complete':raise ValueError('normally completed serial reference required')
        process=json.loads((reference/'native.process.json').read_text())
        if identity(process['pid'])==process['birth']:raise ValueError('original reference worker still live')
        m=json.loads((reference/'manifest.json').read_text());a=json.loads((reference/'assessment.json').read_text());verify(m['input_sha256']);verify(a['artifacts'])
        binary=ROOT/'build/tools/xyce_umfpack_value_gather_001/Xyce';rank_exec=ROOT/'tools/xyce_umfpack/rank_exec.py';mpirun=Path('/usr/bin/mpirun')
        deck=output/'control.spice';raw=output/'control.raw';original=(reference/'control.spice').read_text();deck.write_text(rebind_output(original,raw))
        if rebind_output(deck.read_text(),reference/'control.raw')!=original:raise ValueError('native control changed more than RAW destination')
        paths=[reference/'manifest.json',reference/'assessment.json',reference/'native.log',reference/'control.raw',deck,binary,rank_exec,mpirun,Path(__file__).resolve(),Path(__file__).with_name('compiled_charge_v2.py'),Path(__file__).with_name('assess_selected_detector_prefix.py'),Path(__file__).with_name('assess_selected_detector_phase_probe_v2.py'),Path(__file__).with_name('assess_selected_isolated_control.py')]
        pins={str(p):sha(p) for p in paths};verify(pins)
        save(output/'manifest.json',dict(input_sha256=pins,reference=str(reference),CPUs=cpus,MPI_ranks=len(cpus),memory_reservation_GiB=24,
            per_process_address_space_limit_GiB=12,native_cap_s=10800,automatic_identical_retry=False,
            observed_roles=m['observed_roles'],only_RAW_destination_changed=True,physics_and_tolerances_identical=True,
            numerical_convergence_qualified=False,physical_models_qualified=False,release_ready=False))
        deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+10800;command=[mpirun,'--bind-to','none','-np',len(cpus),'/usr/bin/python3',rank_exec,'--cpus',','.join(map(str,cpus)),'--',binary,'-a','-linsolv','umfpack_reuse',deck]
        save(output/'status.json',dict(state='DCO_MPI_native_running',release_ready=False))
        with lease(len(cpus),24,deadline):execute(command,output/'native.log',deadline,12)
        verify(pins);rows,info=read_prefix(raw,m['observed_roles']);baseline,base_info=read_prefix(reference/'control.raw',m['observed_roles'])
        if info['incomplete_final_sample_discarded'] or info['declared_samples']!=len(rows) or abs(rows[-1][0]-60e-9)>1e-18:raise ValueError('complete finite declared 60 ns output required')
        compared={}
        for column,role in enumerate(m['observed_roles'],1):
            old=transitions(baseline,column);new=transitions(rows,column);compared[role]={}
            for edge in ['rising_ns','falling_ns']:
                x,y=old[edge],new[edge];compared[role][edge]=dict(reference_count=len(x),candidate_count=len(y),counts_match=len(x)==len(y),maximum_edge_difference_ps=max([abs(a-b)*1000 for a,b in zip(x,y)],default=0))
        measured=frequency(rows,20,60);original_frequency=a['frequency'];seconds=elapsed(output/'native.log');reference_seconds=elapsed(reference/'native.log')
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(raw):sha(raw)},native_exit_zero=True,all_saved_values_finite=True,
            waveform=info,reference_waveform=base_info,frequency=measured,reference_frequency=original_frequency,
            frequency_difference_ppm=1e6*(measured['frequency_mhz']/original_frequency['frequency_mhz']-1),edge_comparisons=compared,
            reference_elapsed_s=reference_seconds,candidate_elapsed_s=seconds,wall_speedup=reference_seconds/seconds,
            numerical_convergence_qualified=False,physical_models_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='DCO_MPI_control_assessed',release_ready=False));print(json.dumps(dict(wall_speedup=reference_seconds/seconds,frequency=measured)))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--reference',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--cpus',required=True);a=p.parse_args()
    os.sched_setaffinity(0,{31});os.environ.update(OMP_NUM_THREADS='1',OMP_THREAD_LIMIT='1',OPENBLAS_NUM_THREADS='1')
    run(a.reference.resolve(),a.output.resolve(),[int(s) for s in a.cpus.split(',')])
