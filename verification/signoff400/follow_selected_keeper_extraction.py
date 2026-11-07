"""Wait for one original keeper route, audit it, then extract once if it passes."""
import argparse,json,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import identity,lease
from compiled_charge import execute


def run(route,output):
    output.mkdir(parents=True,exist_ok=False)
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+86400
    owner_file=route/'owner.json';owner=json.loads(owner_file.read_text())
    folder=Path(__file__).resolve().parent
    auditor=folder/'audit_selected_keeper_physical.py';extractor=folder/'extract_selected_keeper_capacitance.py'
    image=ROOT/'build/apptainer/openpll-release-modern.sif'
    files=[Path(__file__).resolve(),owner_file,route/'input_manifest.json',auditor,extractor,image]
    pins={str(p):sha(p)for p in files};verify(pins)
    save(output/'owner.json',dict(pid=__import__('os').getpid(),birth=identity(__import__('os').getpid()),deadline_uptime=deadline))
    save(output/'inputs.json',dict(input_sha256=pins,original_route_owner=owner,max_extractions=1,automatic_identical_retry=False,release_ready=False))
    try:
        while identity(owner['pid'])==owner['birth']:
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('route observation expired; original route untouched')
            save(output/'status.json',dict(state='waiting_for_original_keeper_route',release_ready=False));time.sleep(15)
        verify(pins)
        save(output/'status.json',dict(state='auditing_terminal_keeper_route',release_ready=False))
        audit=output/'physical_audit'
        with lease(1,4,deadline):execute(['apptainer','exec','--bind','/home:/home,/tmp:/tmp',image,
            '/nix/store/ps0r3qpgjh1lqyqacra33rvxsjgkd874-python3-3.13.9-env/bin/python3',auditor,
            '--source',route,'--output',audit],output/'audit.log',deadline,4)
        result=json.loads((audit/'assessment.json').read_text());verify(result['input_sha256']);verify(result['source_input_sha256'])
        if not result['candidate_physical_checks_pass'] or not result['extraction_allowed']:
            save(output/'status.json',dict(state='physical_checks_failed_no_extraction',failed_checks=[k for k,v in result['checks'].items()if not v['pass_check']],release_ready=False));return
        verify(pins)
        save(output/'status.json',dict(state='qualified_candidate_capacitance_extraction_running',release_ready=False))
        execute(['/usr/bin/python3',extractor,'--candidate',audit,'--output',output/'capacitance'],output/'extraction.log',deadline,24)
        verify(pins)
        receipt=output/'capacitance/assessment.json';extraction=json.loads(receipt.read_text());verify(extraction['input_sha256']);verify(extraction['artifacts'])
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p)for p in [audit/'assessment.json',receipt]},
            candidate_capacitance_extraction_complete=True,distributed_R_complete=False,parent_loading_complete=False,
            extracted_native_transient_complete=False,selected=False,release_ready=False))
        save(output/'status.json',dict(state='candidate_capacitance_extracted_review_pending',release_ready=False))
    except BaseException as e:
        save(output/'status.json',dict(state='stopped_without_promotion',reason=repr(e),original_route_not_restarted=True,release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--route',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.route.resolve(),a.output.resolve())
