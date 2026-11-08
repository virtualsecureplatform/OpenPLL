"""Audit a completed resolved-support trace; never read an active native trace."""
import argparse,json,os,time
from pathlib import Path
from common_v3 import save,sha,verify
from resources import identity,lease
from audit_keeper_native_R_contraction import compare
from audit_magic_overlap_support import reconstruct as overlaps
from audit_magic_fringe_support import reconstruct as fringes


def run(flat,source,output,wait):
    output.mkdir(exist_ok=False,parents=True);os.sched_setaffinity(0,{29})
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+172800
    try:
        while True:
            state=json.loads((source/'status.json').read_text())['state']
            if state=='flat_ground_lifecycle_trace_complete_audit_pending' and (source/'assessment.json').exists():break
            if state=='stopped_without_qualification':raise RuntimeError('native trace stopped')
            owner=json.loads((source/'owner.json').read_text())
            if identity(owner['pid'])!=owner['birth']:raise RuntimeError('native trace owner gone without completed receipt')
            if not wait:raise RuntimeError('native trace incomplete')
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('trace observation deadline')
            save(output/'status.json',dict(state='waiting_for_completed_resolved_trace',release_ready=False));time.sleep(10)
        receipts=[p/'assessment.json' for p in [flat,source]]
        a,b=[json.loads(p.read_text()) for p in receipts]
        if not b['native_process_completed'] or not b['resolved_overlap_and_fringe_trace_available'] or b['input_sha256'].get(str(receipts[0]))!=sha(receipts[0]):raise ValueError('matching completed resolved-support extraction required')
        pins={}
        for r in [a,b]:
            for path,digest in {**r['input_sha256'],**r['artifacts']}.items():
                if path in pins and pins[path]!=digest:raise ValueError('conflicting artifact identities')
                pins[path]=digest
        helpers=['common_v3.py','resources.py','audit_keeper_native_R_contraction.py','native_spice_comments.py','audit_magic_overlap_support.py','audit_magic_fringe_support.py','audit_magic_coupling_geometry_trace.py','magic_fringe_kernel.py']
        pins.update({str(p):sha(p) for p in [*receipts,Path(__file__).resolve(),*[Path(__file__).with_name(n) for n in helpers]]})
        with lease(1,8,time.clock_gettime(time.CLOCK_BOOTTIME)+21600):
            verify(pins)
            save(output/'status.json',dict(state='auditing_completed_resolved_trace',release_ready=False))
            circuit=compare((flat/'capacitance.spice').read_text(),(source/'pilot.spice').read_text())
            if not circuit['exact_device_and_C_contraction_verified'] or circuit['wire_R_cards']!=0:raise ValueError('logging changed C-only circuit')
            overlap=overlaps(source/'coupling.jsonl');fringe=fringes(source/'coupling.jsonl')
            verify(pins)
            save(output/'assessment.json',dict(input_sha256=pins,artifacts={},circuit=circuit,overlap=overlap,fringe=fringe,completed_native_trace_audited=True,ground_geometry_qualified=False,pointwise_capacitance_placement_qualified=False,distributed_wire_R_qualified=False,native_simulation_allowed=False,release_ready=False))
        save(output/'status.json',dict(state='resolved_trace_support_diagnostics_complete',release_ready=False))
    except BaseException as e:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(e),native_children_unchanged=True,release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['flat','source','output']:p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--wait',action='store_true');a=p.parse_args();run(a.flat.resolve(),a.source.resolve(),a.output.resolve(),a.wait)
