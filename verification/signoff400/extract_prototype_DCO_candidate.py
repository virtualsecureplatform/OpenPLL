"""Extract stock hierarchical capacitance from an isolated, pinned DCO route."""
import argparse
import json
import os
from pathlib import Path
import time
from common_v3 import ROOT, save, sha, verify
from resources import lease, identity
from compiled_charge import execute


def run(candidate, output):
    receipt=candidate/'assessment.json';r=json.loads(receipt.read_text())
    verify(r['input_sha256']);verify(r['artifacts'])
    if not r['isolated_route_completed'] or r['physical_candidate_selected']:
        raise ValueError('isolated routed candidate required')
    gds=[Path(p) for p in r['artifacts'] if p.endswith('.gds')]
    if len(gds)!=1:raise ValueError('unique pinned candidate GDS required')
    gds=gds[0];top=gds.stem
    output.mkdir(parents=True,exist_ok=False)
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline))
    image=ROOT/'build/apptainer/openpll-release-modern.sif'
    worker=ROOT/'verification/signoff400/extract_prototype_analog_capacitance_v2.py'
    config=output/'config.json';save(config,dict(gds=str(gds),tops=[top],output=str(output),deadline_uptime=deadline))
    pins={str(p):sha(p) for p in (receipt,gds,image,worker,config,Path(__file__).resolve())}
    save(output/'input_manifest.json',dict(input_sha256=pins))
    os.environ.update(GOMAXPROCS='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
    try:
        save(output/'status.json',dict(state='waiting_for_extraction_resources',release_ready=False))
        with lease(1,16,deadline):
            save(output/'status.json',dict(state='native_stock_capacitance_extraction_running',release_ready=False))
            execute(['apptainer','exec','--bind','/home:/home,/tmp:/tmp',image,'/usr/bin/python3',worker,'--inside',config],output/'worker.log',deadline,16)
        verify(pins)
        native=output/'native_assessment.json';n=json.loads(native.read_text());verify(n['input_sha256']);verify(n['artifacts'])
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(native):sha(native)},
            stock_hierarchical_analog_capacitance_extracted=True,device_geometry_review_complete=False,
            parent_loading_complete=False,distributed_R_complete=False,validated_for_prototype=False,release_ready=False))
        save(output/'status.json',dict(state='candidate_capacitance_extracted_review_pending',release_ready=False))
    except BaseException as exc:
        save(output/'status.json',dict(state='stopped_without_promotion',reason=repr(exc),release_ready=False));raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--candidate',required=True,type=Path);p.add_argument('--output',required=True,type=Path)
    a=p.parse_args();run(a.candidate.resolve(),a.output.resolve())
