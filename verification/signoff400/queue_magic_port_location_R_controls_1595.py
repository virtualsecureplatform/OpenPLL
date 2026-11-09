"""Two bounded native resistance export controls, preserving any failure."""
import json,os,time
from runtime_common import ROOT,save,sha
from resources import identity,lease
from compiled_charge_v2 import execute
from audit_keeper_native_R_contraction import parse

def run():
    base=ROOT/'build';engine=base/'tools/magic_port_location_candidate_1594'
    output=base/'signoff400/selected_magic_port_location_R_controls_1595';output.mkdir(exist_ok=False)
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())) )
    owner=json.loads((engine/'owner.json').read_text());deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+86400
    try:
        while True:
            state=json.loads((engine/'status.json').read_text())['state']
            if state=='isolated_ground_support_trace_build_complete':break
            if state=='stopped_without_qualification' or identity(owner['pid'])!=owner['birth']:raise RuntimeError('combined build not completed')
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('build observation deadline')
            save(output/'status.json',dict(state='waiting_for_live_combined_build',release_ready=False));time.sleep(10)
        binary=engine/'install/bin/magic';receipt=engine/'assessment.json';r=json.loads(receipt.read_text())
        if r['artifacts'][str(binary)]!=sha(binary):raise ValueError('native engine digest differs')
        tech='/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae/sky130A/libs.tech/magic/sky130A.tech'
        probe=ROOT/'tools/magic_rcx/coupling_grounding_R_threshold1_probe.tcl'
        save(output/'inputs.json',dict(input_sha256={str(p):sha(p) for p in [receipt,binary,probe,__file__]},maximum_native_cases=2,automatic_identical_retry=False,release_ready=False))
        results=[];artifacts={}
        with lease(1,2,deadline):
            for coupling in [0,1]:
                case=output/f'coupling{coupling}';case.mkdir();rc=case/'minimal.magicrc';rc.write_text(f'tech load {{{tech}}}\n')
                script=case/'run.tcl';script.write_text(f'cd {{{case}}}\nsource {{{probe}}}\n')
                save(output/'status.json',dict(state='running_native_R_control',coupling=coupling,release_ready=False))
                execute(['env',f'OPENPLL_TEST_COUPLING={coupling}',str(binary),'-nowrapper','-dnull','-noconsole','-rcfile',str(rc),str(script)],case/'native.log',time.clock_gettime(time.CLOCK_BOOTTIME)+120,2)
                after=parse((case/'after.spice').read_text());positive=sum(v>0 for a,b,v in after['resistors'])
                if not positive:raise ValueError('fixture did not emit nonzero wire resistance')
                results.append(dict(coupling=bool(coupling),positive_R_edges=positive,before_after_byte_identical=(case/'before.spice').read_bytes()==(case/'after.spice').read_bytes()))
                artifacts.update({str(p):sha(p) for p in case.iterdir() if p.is_file()})
        save(output/'assessment.json',dict(results=results,artifacts=artifacts,full_C_contraction_verified=False,wire_R_geometry_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='native_R_controls_completed',release_ready=False))
    except Exception as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise

if __name__=='__main__':run()
