"""Run four contact controls only after the live combined build completes."""
import json,os,time
from runtime_common import ROOT,save,sha
from resources import identity
from probe_magic_combined_contact_1588 import run as probe
from audit_magic_fringe_support import reconstruct


def run():
    output=ROOT/'build/signoff400/selected_magic_combined_contact_queue_1589';output.mkdir(exist_ok=False)
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())) )
    build=ROOT/'build/tools/magic_contact_residue_R_candidate_1587'
    owner=json.loads((build/'owner.json').read_text());deadline=time.monotonic()+86400
    try:
        while True:
            state=json.loads((build/'status.json').read_text())['state']
            if state=='isolated_ground_support_trace_build_complete' and (build/'assessment.json').exists():break
            if state=='stopped_without_qualification':raise RuntimeError('combined build stopped')
            if identity(owner['pid'])!=owner['birth']:raise RuntimeError('build owner gone without completed receipt')
            if time.monotonic()>=deadline:raise TimeoutError('build observation deadline')
            save(output/'status.json',dict(state='waiting_for_live_combined_build',release_ready=False));time.sleep(10)
        probe()
        candidate=ROOT/'build/signoff400/selected_magic_combined_contact_controls_1588'
        previous=ROOT/'build/signoff400/selected_magic_contact_layout_candidate_1571'
        results=[]
        for contact in [0,1]:
            for shield in [0,1]:
                name=f'contact{contact}_shield{shield}'
                integral=reconstruct(candidate/name/'coupling.jsonl')
                if (candidate/name/'probe.spice').read_bytes()!=(previous/name/'probe.spice').read_bytes():
                    raise ValueError('C-only control changed after resistance patches: '+name)
                results.append(dict(case=name,integrals=integral,contact_corrected_SPICE_unchanged=True))
        save(output/'assessment.json',dict(input_sha256={str(p):sha(p) for p in [candidate/'assessment.json',previous/'assessment.json',__file__]},results=results,
             all_four_native_integrals_pass=True,all_four_C_only_SPICE_unchanged=True,wire_R_qualified=False,release_ready=False))
        save(output/'status.json',dict(state='combined_contact_controls_pass',release_ready=False))
    except Exception as error:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(error),release_ready=False));raise

if __name__=='__main__':run()
