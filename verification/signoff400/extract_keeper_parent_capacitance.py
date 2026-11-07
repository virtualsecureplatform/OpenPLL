"""Extract one full checked keeper parent in the current pinned container."""
import argparse,json,os,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from resources import identity,lease
from extract_prototype_assembly_capacitance import inside


def run(layout,output):
    receipt=layout/'assessment.json';proof=layout/'lvs_proof/assessment.json'
    a,p=[json.loads(x.read_text())for x in [receipt,proof]]
    for r in [a,p]:verify(r['input_sha256']);verify(r['artifacts'])
    if not all(a[k]for k in ['assembled_drc_pass','assembled_lvs_pass','all_three_macros_expanded'])or not p['assembled_lvs_pass']or p['input_sha256'].get(str(receipt))!=sha(receipt):
        raise ValueError('same filled parent must pass expanded DRC/LVS')
    gds=layout/'assembly.gds'
    if a['artifacts'].get(str(gds))!=sha(gds):raise ValueError('checked filled GDS differs')
    output.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+86400
    os.sched_setaffinity(0,{23});os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline,wall_limit_s=86400,cpu_slots=1,memory_GiB=16,automatic_identical_retry=False))
    config=output/'config.json';save(config,dict(gds=str(gds),tops=['IntegerPLL_400MHz_PrototypeTop'],output=str(output),deadline_uptime=deadline))
    worker=Path(__file__).with_name('extract_prototype_assembly_capacitance.py')
    image=ROOT/'build/apptainer/openpll-release-modern.sif'
    pins={str(x):sha(x)for x in [Path(__file__).resolve(),worker,receipt,proof,gds,config,image]}
    save(output/'input_manifest.json',dict(input_sha256=pins,scope='full checked filled keeper parent; stock hierarchical capacitance',release_ready=False))
    try:
        save(output/'status.json',dict(state='waiting_for_full_parent_capacitance_resources',release_ready=False))
        with lease(1,16,deadline):
            save(output/'status.json',dict(state='full_keeper_parent_capacitance_extraction_running',release_ready=False))
            inside(config)
        native=output/'native_assessment.json';n=json.loads(native.read_text());verify(n['input_sha256']);verify(n['artifacts']);verify(pins)
        if not n['full_assembly_capacitance_extracted']:raise ValueError('full native parent extraction missing')
        save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(native):sha(native),**n['artifacts']},
            full_checked_parent_capacitance_extracted=True,completed_native_inputs_and_artifacts_verified_inside_image=True,
            source_parent_GDS_sha256=sha(gds),parent_loading_complete=False,distributed_R_complete=False,
            passivity_qualified=False,native_model_qualified=False,selected=False,release_ready=False))
        save(output/'status.json',dict(state='full_keeper_parent_capacitance_extracted_review_pending',release_ready=False))
    except BaseException as e:
        save(output/'status.json',dict(state='stopped_without_qualification',reason=repr(e),release_ready=False));raise

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--layout',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.layout.resolve(),a.output.resolve())
