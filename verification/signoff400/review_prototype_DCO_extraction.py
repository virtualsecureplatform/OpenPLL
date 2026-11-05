"""Verify completed native extraction in its pinned container without rerunning Magic."""
import argparse,json,os,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from compiled_charge import execute
from resources import lease


def inside(native,result):
    r=json.loads(native.read_text());verify(r['input_sha256']);verify(r['artifacts'])
    if not r['stock_hierarchical_analog_capacitance_extracted']:raise ValueError('native extraction incomplete')
    save(result,dict(native_receipt_sha256=sha(native),native_inputs_and_artifacts_verified=True))


def run(source,output):
    native=source/'native_assessment.json';image=ROOT/'build/apptainer/openpll-release-modern.sif'
    manifest=source/'input_manifest.json';m=json.loads(manifest.read_text());verify(m['input_sha256'])
    output.mkdir(parents=True,exist_ok=False);result=output/'native_review.json'
    pins={str(p):sha(p) for p in (native,manifest,image,Path(__file__).resolve())}
    os.environ.update(GOMAXPROCS='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    with lease(1,4,deadline):execute(['apptainer','exec','--bind','/home:/home,/tmp:/tmp',image,'/usr/bin/python3',Path(__file__).resolve(),'--inside',native,'--result',result],output/'review.log',deadline,4)
    rr=json.loads(result.read_text())
    if not rr['native_inputs_and_artifacts_verified'] or rr['native_receipt_sha256']!=sha(native):raise ValueError('native review mismatch')
    r=json.loads(native.read_text());verify(r['artifacts']);verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(result):sha(result),**r['artifacts']},
        completed_native_extraction_verified_in_pinned_image=True,stock_hierarchical_analog_capacitance_extracted=True,
        source_extraction_directory=str(source),native_simulation_repeated=False,
        parent_loading_complete=False,distributed_R_complete=False,device_geometry_review_complete=False,validated_for_prototype=False,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--inside',type=Path);p.add_argument('--result',type=Path);p.add_argument('--source',type=Path);p.add_argument('--output',type=Path)
    a=p.parse_args()
    if a.inside:inside(a.inside,a.result)
    else:run(a.source.resolve(),a.output.resolve())
