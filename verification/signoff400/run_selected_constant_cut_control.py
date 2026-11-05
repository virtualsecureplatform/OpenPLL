"""Benchmark an exact constant-capacitor-cut elimination against its serial run."""
import argparse,json,os,re,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import identity,lease
from compiled_charge_v2 import execute
from assess_selected_detector_prefix import read_prefix
from assess_selected_detector_phase_probe_v4 import transitions
from assess_selected_isolated_control import frequency
from run_selected_dco_parallel_control import elapsed


def run(reference,output,cpu):
    for name in ['owner.json','native.log','native.process.json','control.raw','assessment.json']:
        if (output/name).exists():raise FileExistsError(output/name)
    deck=output/'control.spice'
    libraries=re.findall(r'^\.lib "([^"]+)" tt$',deck.read_text(),re.MULTILINE)
    if len(libraries)!=1 or not Path(libraries[0]).is_file():raise EnvironmentError('pinned release container and PDK required')
    os.sched_setaffinity(0,{cpu})
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    save(output/'status.json',dict(state='preparing_constant_cut_native_control',release_ready=False))
    try:
        if json.loads((reference/'status.json').read_text())['state']!='real_driver_DCO_diagnostic_complete':raise ValueError('normally completed serial reference required')
        original=json.loads((reference/'manifest.json').read_text());proof=output/'elimination.json';p=json.loads(proof.read_text())
        verify(original['input_sha256']);verify(p['input_sha256']);verify(p['artifacts'])
        if p['input_sha256'].get(str(reference/'manifest.json'))!=sha(reference/'manifest.json'):raise ValueError('elimination belongs to another reference')
        binary=ROOT/'build/tools/xyce_umfpack_value_gather_001/Xyce'
        paths=[reference/'manifest.json',reference/'assessment.json',reference/'native.log',reference/'control.raw',proof,
            deck,output/'devices.spice',output/'sources.spice',binary,Path(__file__).resolve(),
            Path(__file__).with_name('compiled_charge_v2.py'),Path(__file__).with_name('run_selected_dco_parallel_control.py'),
            Path(__file__).with_name('assess_selected_detector_prefix.py'),Path(__file__).with_name('assess_selected_detector_phase_probe_v4.py'),
            Path(__file__).with_name('assess_selected_isolated_control.py')]
        pins={str(path):sha(path) for path in paths};verify(pins)
        save(output/'manifest.json',dict(input_sha256=pins,reference=str(reference),CPU=cpu,MPI_ranks=1,memory_GiB=16,
            native_cap_s=10800,automatic_identical_retry=False,observed_roles=original['observed_roles'],
            eliminated_constant_cut_nodes=p['eliminated_node_count'],retained_differential_equations_identical=True,
            solver_tolerances_unchanged=True,absolute_capacitor_energy_and_removed_source_currents_preserved=False,
            numerical_convergence_qualified=False,physical_models_qualified=False,release_ready=False))
        deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+10800
        save(output/'status.json',dict(state='constant_cut_native_control_running',release_ready=False))
        with lease(1,16,deadline):execute([binary,'-a','-linsolv','umfpack_reuse',deck],output/'native.log',deadline,16)
        verify(pins);rows,info=read_prefix(output/'control.raw',original['observed_roles']);baseline,base_info=read_prefix(reference/'control.raw',original['observed_roles'])
        if info['declared_samples']!=len(rows) or info['incomplete_final_sample_discarded'] or abs(rows[-1][0]-60e-9)>1e-18:raise ValueError('complete finite native 60 ns output required')
        comparisons={}
        for column,role in enumerate(original['observed_roles'],1):
            a,b=transitions(baseline,column),transitions(rows,column);comparisons[role]={}
            for edge in ['rising_ns','falling_ns']:
                x,y=a[edge],b[edge];comparisons[role][edge]=dict(reference_count=len(x),candidate_count=len(y),counts_match=len(x)==len(y),maximum_edge_difference_ps=max([abs(t-u)*1000 for t,u in zip(x,y)],default=0))
        measured,old=frequency(rows,20,60),frequency(baseline,20,60);seconds,previous=elapsed(output/'native.log'),elapsed(reference/'native.log')
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(output/'control.raw'):sha(output/'control.raw')},
            native_exit_zero=True,all_saved_values_finite=True,waveform=info,reference_waveform=base_info,frequency=measured,
            reference_frequency=old,frequency_difference_ppm=1e6*(measured['frequency_mhz']/old['frequency_mhz']-1),
            edge_comparisons=comparisons,candidate_elapsed_s=seconds,reference_elapsed_s=previous,wall_speedup=previous/seconds,
            retained_differential_equation_reduction=True,numerical_convergence_qualified=False,physical_models_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='constant_cut_native_control_assessed',release_ready=False))
    except BaseException as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    for name in ['reference','output']:parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--cpu',type=int,choices=range(16,32),required=True)
    args=parser.parse_args();os.environ.update(OMP_NUM_THREADS='1',OMP_THREAD_LIMIT='1',OPENBLAS_NUM_THREADS='1')
    run(args.reference.resolve(),args.output.resolve(),args.cpu)
