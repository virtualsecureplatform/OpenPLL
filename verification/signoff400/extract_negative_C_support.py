"""Extract exact P1 support triangles for all identified negative C states."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import time
from common import ROOT,save,sha,verify
from compiled_charge import execute
from resources import identity,lease


def run(output,controls):
    output.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline,
         cpu_slots=8,memory_GiB=4,automatic_identical_retry=False))
    def status(state,**more):save(output/'status.json',dict(state=state,release_qualified=False,**more))
    try:
        control=controls/'assessment.json';c=json.loads(control.read_text());verify(c['input_sha256'])
        binary=controls/'extract_negative_C_support'
        if not c['negative_C_P1_support_controls_pass'] or sha(binary)!=c['artifacts'][str(binary)]:
            raise ValueError('matching independently controlled support extractor required')
        base=ROOT/'build/signoff400';target_receipt=base/'startup_timing_negative_C_fields_002/assessment.json'
        t=json.loads(target_receipt.read_text());targets=Path(t['targets'])
        if not t['all_negative_diagonal_states_resolved_to_original_R_fields']:
            raise ValueError('complete negative node namespace required')
        projection=base/'startup_timing_full_spatial_projection_002/assessment.json';p=json.loads(projection.read_text())
        source_config=projection.parent/'config.json';geometry=json.loads(source_config.read_text())['geometry']
        paths=[control,binary,target_receipt,targets,projection,source_config,Path(__file__).resolve()]
        mesh_paths=[Path(geometry[k]) for k in ('R_index','R_bundles')]+list(map(Path,geometry['R_parts']))
        paths+=mesh_paths
        with lease(8,4,deadline):
            status('hashing_pinned_negative_state_and_R_mesh_inputs')
            with ThreadPoolExecutor(max_workers=8) as pool:pins=dict(zip(map(str,paths),pool.map(sha,paths)))
            if pins[str(targets)]!=t['artifacts'][str(targets)] or any(pins[str(path)]!=p['input_sha256'][str(path)] for path in mesh_paths):
                raise ValueError('support geometry differs from completed source projection')
            save(output/'input_manifest.json',dict(input_sha256=pins))
            cfg,triangles,report=output/'config.json',output/'triangles.jsonl',output/'report.json'
            save(cfg,dict(targets=str(targets),geometry=geometry,threads=8,deadline_uptime=deadline,
                          triangles=str(triangles),report=str(report)))
            status('scanning_all_R_triangles_for_exact_negative_node_support')
            execute([binary,cfg],output/'scan.log',deadline,4);found=json.loads(report.read_text())
            if found['target_nodes']!=sum(len(r['original_voltage_nodes']) for r in json.loads(targets.read_text())['negative_nodes']):
                raise ValueError('support/negative node count differs')
            verify(pins)
            save(output/'assessment.json',dict(input_sha256=pins,
                 artifacts={str(p):sha(p) for p in (cfg,triangles,report)},results=found,
                 triangles=str(triangles),complete_negative_C_P1_support_extracted=True,
                 full_operator_support_selection_certified=False,physical_RC_qualified=False,release_qualified=False))
            status('negative_C_P1_support_complete')
    except BaseException as error:
        status('stopped_without_promotion',reason=repr(error));raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True,type=Path)
    p.add_argument('--controls',required=True,type=Path);a=p.parse_args();run(a.output.resolve(),a.controls.resolve())
