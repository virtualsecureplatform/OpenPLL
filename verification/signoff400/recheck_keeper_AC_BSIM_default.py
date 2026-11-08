"""Recheck the completed keeper AC matrix with only the corrected BSIM executable."""
import argparse,json,math,os,shutil,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import lease,identity
from compiled_charge_v2 import execute
from revalidate_keeper_primitive_AC_v2 import numeric

def run(previous,backend,output):
    receipt=previous/'assessment.json';build=backend.parent/'assessment.json';p,b=[json.loads(q.read_text())for q in [receipt,build]]
    for r in [p,b]:verify(r['input_sha256']);verify(r['artifacts'])
    if not p['all_twenty_native_AC_analyses_complete'] or sha(backend)!=b['binary_sha256'] or not b['baseline_archive_relink_exactly_reproduces_checked_binary']:raise ValueError('completed controls and checked new executable required')
    if b['changed_archive_members']!=['N_DEV_MOSFET_B4p61.C.o','N_DEV_MOSFET_B4p70.C.o','N_DEV_MOSFET_B4p82.C.o']:raise ValueError('only defaulting correction objects may change')
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{28});os.environ.update(OMP_NUM_THREADS='1',OMP_THREAD_LIMIT='1',OPENBLAS_NUM_THREADS='1');deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+900
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())));pins={str(q):sha(q)for q in [receipt,build,backend,Path(__file__).resolve(),Path(__file__).with_name('revalidate_keeper_primitive_AC_v2.py')]};results=[];artifacts={}
    jobs=[]
    for corner in ['tt','ff','ss','sf','fs']:
        for excited in ['gate','drain']:
            name=corner+'_'+excited;folder=output/name;folder.mkdir();source=previous/name/'xy.spice';reference=previous/name/'reference.tsv';candidate=folder/'xy.spice';shutil.copy2(source,candidate)
            if p['input_sha256'].get(str(source))!=sha(source) or p['artifacts'].get(str(reference))!=sha(reference):raise ValueError('same frozen deck/reference required')
            pins.update({str(q):sha(q)for q in [source,reference,candidate]});jobs.append((corner,excited,folder,candidate,reference))
    save(output/'inputs.json',dict(input_sha256=pins,candidate_backend=str(backend),previous_completed_comparison=str(previous),all_reference_outputs_reused_without_native_retry=True,all_electrical_decks_byte_identical=True,CPU=28,memory_GiB=4,native_cap_s=900,maximum_new_native_cases=10,automatic_identical_retry=False,release_ready=False))
    try:
        verify(pins)
        with lease(1,4,deadline):
            for corner,excited,folder,deck,reference in jobs:
                save(output/'status.json',dict(state='rechecking_keeper_AC_with_BSIM_default_correction',corner=corner,excited_terminal=excited,release_ready=False));execute([backend,'-linsolv','umfpack_reuse','-o',folder/'candidate',deck],folder/'xy.log',deadline,4)
                n=numeric(reference,1+4*429,3);x=numeric(folder/'candidate.FD.prn',2+4*429);observations=[]
                for frequency,a,c in zip([25e6,400e6],[n[0],n[-1]],x):
                    if abs(a[0]/frequency-1)>1e-12 or abs(c[1]/frequency-1)>1e-12:raise ValueError('AC frequency alignment mismatch')
                    for i in range(429):
                        for terminal,offset in [('gate',0),('drain',2)]:
                            j=4*i+offset;ref=complex(a[1+j],a[2+j]);value=complex(c[2+j],c[3+j]);observations.append(dict(geometry=i,observed_terminal=terminal,frequency_Hz=frequency,reference_real_A=ref.real,reference_imag_A=ref.imag,candidate_real_A=value.real,candidate_imag_A=value.imag,complex_current_relative_error=abs(value-ref)/max(abs(ref),1e-18),reactive_current_difference_equivalent_F=abs(value.imag-ref.imag)/(2*math.pi*frequency)))
                detail=folder/'comparisons.json';save(detail,observations);results.append(dict(corner=corner,excited_terminal=excited,observations=len(observations),maximum_complex_current_relative_error=max(r['complex_current_relative_error']for r in observations),maximum_reactive_difference_equivalent_fF=1e15*max(r['reactive_current_difference_equivalent_F']for r in observations)))
                artifacts.update({str(q):sha(q)for q in [detail,folder/'candidate.FD.prn',folder/'xy.log']});save(output/'progress.json',results)
        verify(pins);save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,results=results,all_ten_new_native_AC_analyses_complete=True,all_17160_current_geometry_observations_compared=True,unique_MOS_parameter_sets=429,gate_DC_V=.9,drain_DC_V=.9,temperature_C=27,frequencies_Hz=[25e6,400e6],base_backend_comparison_results=p['results'],electrical_decks_unchanged=True,reference_outputs_unchanged=True,full_bias_range_covered=False,small_signal_model_qualified=False,transient_qualified=False,full_PLL_model_qualified=False,release_ready=False));save(output/'status.json',dict(state='corrected_backend_keeper_midpoint_AC_comparison_complete',release_ready=False))
    except BaseException as e:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(e),automatic_identical_retry=False,release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['previous','backend','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.previous.resolve(),a.backend.resolve(),a.output.resolve())
