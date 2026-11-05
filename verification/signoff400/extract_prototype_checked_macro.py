"""Extract stock capacitance from a checked digital macro in a pinned image."""
import argparse,json,os,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import lease,identity
from compiled_charge import execute


def inside(config):
    cfg=json.loads(config.read_text());output=Path(cfg['output']);audit=json.loads(Path(cfg['audit']).read_text())
    verify(audit['sha256'])
    if not (audit['magic_drc_rectangles']==0 and audit['lvs_unique_match'] and audit['antenna_net_violations']==0 and audit['antenna_pin_violations']==0):raise ValueError('DRC/LVS/antenna checked macro required')
    gds=Path(cfg['gds'])
    if audit['sha256'].get(str(gds))!=sha(gds):raise ValueError('checked GDS identity mismatch')
    from extract_prototype_analog_capacitance_v2 import inside as extract
    extract(config)
    native=output/'native_assessment.json';r=json.loads(native.read_text());verify(r['input_sha256']);verify(r['artifacts'])
    save(output/'image_verification.json',dict(native_receipt_sha256=sha(native),all_native_inputs_and_artifacts_verified=True))


def run(route,output):
    audit=route/'signoff/assessment.json';a=json.loads(audit.read_text());receipt=route/'assessment.json';r=json.loads(receipt.read_text());verify(r['artifacts'])
    gds=route/'signoff/route.gds';image=ROOT/'build/apptainer/openpll-release-modern.sif'
    if a['sha256'].get(str(route/'route.odb'))!=sha(route/'route.odb'):raise ValueError('checked layout uses another route')
    output.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline))
    config=output/'config.json';save(config,dict(audit=str(audit),gds=str(gds),tops=['IntegerPLL_ProgrammedCore'],output=str(output),deadline_uptime=deadline))
    paths=[audit,receipt,route/'route.odb',gds,image,config,Path(__file__).resolve(),Path(__file__).with_name('extract_prototype_analog_capacitance_v2.py')]
    pins={str(p):sha(p) for p in paths};save(output/'input_manifest.json',dict(input_sha256=pins))
    os.environ.update(GOMAXPROCS='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
    try:
        save(output/'status.json',dict(state='waiting_for_checked_macro_extraction_lease',release_ready=False))
        with lease(1,16,deadline):
            save(output/'status.json',dict(state='native_stock_capacitance_extraction_running',release_ready=False))
            execute(['apptainer','exec','--bind','/home:/home,/tmp:/tmp',image,'/usr/bin/python3',Path(__file__).resolve(),'--inside',config],output/'worker.log',deadline,16)
        native=output/'native_assessment.json';proof=output/'image_verification.json';p=json.loads(proof.read_text())
        if not p['all_native_inputs_and_artifacts_verified'] or p['native_receipt_sha256']!=sha(native):raise ValueError('native image verification mismatch')
        nr=json.loads(native.read_text());verify(nr['artifacts']);verify(pins)
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(native):sha(native),str(proof):sha(proof),**nr['artifacts']},
            candidate_source_sha256=r['candidate_source_sha256'],checked_route_sha256=sha(receipt),source_extraction_directory=str(output),
            completed_native_extraction_verified_in_pinned_image=True,stock_hierarchical_analog_capacitance_extracted=True,
            parent_loading_complete=False,distributed_R_complete=False,device_geometry_review_complete=False,validated_for_prototype=False,release_ready=False))
        save(output/'status.json',dict(state='checked_macro_capacitance_extracted_review_pending',release_ready=False))
    except BaseException as exc:
        save(output/'status.json',dict(state='stopped_without_promotion',reason=repr(exc),release_ready=False));raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--inside',type=Path);p.add_argument('--route',type=Path);p.add_argument('--output',type=Path)
    a=p.parse_args()
    if a.inside:inside(a.inside)
    else:run(a.route.resolve(),a.output.resolve())
