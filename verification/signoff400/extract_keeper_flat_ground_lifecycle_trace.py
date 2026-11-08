"""One bounded native combined ground/coupling trace on the unchanged checked flat GDS."""
import argparse,json,os,time
from pathlib import Path
from common_v3 import save,sha,verify
from resources import lease,identity
from compiled_charge_v2 import execute
from replay_keeper_flat_signed_C import TECH
from extract_keeper_flat_geometry_C import FLAT

def run(flat,engine,controls,output):
    receipts=[p/'assessment.json'for p in [flat,engine,controls]];f,e,c=[json.loads(p.read_text())for p in receipts]
    for r in [f,e,c]:verify(r['input_sha256']);verify(r['artifacts'])
    if not c['numeric_ground_lifecycle_verified'] or not c['all_six_native_controls_complete'] or not c['logging_preserves_tested_circuits'] or e['capacitance_equations_modified'] or c['input_sha256'].get(str(receipts[1]))!=sha(receipts[1]):raise ValueError('same independently checked logging-only engine required')
    binary=Path(e['installed_executable']);gds=flat/'flat.gds';output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{27});os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1');deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+1800
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())));rc=output/'minimal.magicrc';rc.write_text(f'tech load {{{TECH}}}\ndrc off\ncrashbackups disable\nlocking disable\n');script=output/'extract.tcl';model=output/'pilot.spice';trace=output/'coupling.jsonl';os.environ['OPENPLL_COUPLING_TRACE']=str(trace)
    script.write_text(f'''cd {{{output}}}
if {{[catch {{
gds read {{{gds}}}
load {FLAT}
select top cell
extract style ngspice()
extract do local
extract do capacitance
extract do coupling
extract no resistance
extract warn all
extract all
ext2spice lvs
ext2spice hierarchy off
ext2spice subcircuit top on
ext2spice short resistor
ext2spice cthresh -1e100
ext2spice extresist off
ext2spice -o {{{model}}} {FLAT}.ext
feedback save {{{output/'feedback.txt'}}}
}} error]}} {{puts stderr $error; exit 1}}
quit -noprompt
''')
    folder=Path(__file__).resolve().parent;pins={str(p):sha(p)for p in [*receipts,gds,binary,TECH,rc,script,Path(__file__).resolve(),folder/'compiled_charge_v2.py',folder/'extract_keeper_flat_geometry_C.py']};save(output/'inputs.json',dict(input_sha256=pins,source_GDS_unchanged=True,full_RC_extraction_mode=False,distributed_R_export=False,coupling_trace=str(trace),geometry_is_search_support_only=True,CPU=27,memory_GiB=16,native_cap_s=1800,maximum_native_cases=1,automatic_identical_retry=False,release_ready=False))
    try:
        verify(pins);save(output/'status.json',dict(state='checked_flat_ground_lifecycle_trace_running',release_ready=False))
        with lease(1,16,deadline):execute([binary,'-nowrapper','-dnull','-noconsole','-rcfile',rc,script],output/'native.log',deadline,16)
        verify(pins);files=[model,trace,output/(FLAT+'.ext'),output/'native.log',output/'feedback.txt']
        if any(not p.exists()for p in files):raise ValueError('complete native trace artifacts required')
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p)for p in files},native_process_completed=True,coupling_geometry_trace_available=True,numeric_ground_lifecycle_trace_available=True,numeric_ground_lifecycle_verified=False,source_GDS_sha256=sha(gds),trace_ledger_reconstruction_verified=False,full_circuit_equivalence_verified=False,ground_capacitance_geometry_traced=False,pointwise_placement_qualified=False,distributed_wire_R_qualified=False,native_simulation_allowed=False,release_ready=False));save(output/'status.json',dict(state='flat_ground_lifecycle_trace_complete_audit_pending',release_ready=False))
    except BaseException as ex:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(ex),automatic_identical_retry=False,release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['flat','engine','controls','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve()for n in ['flat','engine','controls','output']))
