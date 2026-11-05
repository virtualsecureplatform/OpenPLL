"""Trace original operators intersecting every exact negative-node P1 support."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import tempfile
import time
from common import ROOT,save,sha,verify
from compiled_charge import execute
from resources import identity,lease


def run(output,controls):
    output.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    scratch=Path(tempfile.mkdtemp(prefix='openpll-negative-C-operators-',dir='/tmp'))
    (output/'native').symlink_to(scratch,target_is_directory=True)
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),deadline_uptime=deadline,
         cpu_slots=16,memory_GiB=8,automatic_identical_retry=False,retained_local_scratch=str(scratch)))
    def status(state,**more):save(output/'status.json',dict(state=state,release_qualified=False,**more))
    try:
        control=controls/'assessment.json';c=json.loads(control.read_text());verify(c['input_sha256'])
        binary=controls/'select_negative_C_operators'
        if not c['negative_C_operator_selector_controls_pass'] or sha(binary)!=c['artifacts'][str(binary)]:
            raise ValueError('independently controlled operator selector required')
        base=ROOT/'build/signoff400';support=base/'startup_timing_negative_C_support_001/assessment.json'
        s=json.loads(support.read_text());triangles=Path(s['triangles'])
        if not s['complete_negative_C_P1_support_extracted']:raise ValueError('complete P1 target support required')
        projection=base/'startup_timing_full_spatial_projection_002/assessment.json';p=json.loads(projection.read_text())
        source_config=projection.parent/'config.json';source=json.loads(source_config.read_text())
        if not p['full_operator_coverage'] or not p['spatial_operator_projection_complete']:
            raise ValueError('complete original projection required')
        expected={str(triangles):s['artifacts'][str(triangles)]}
        for task in source['shards']:
            for key in ('operators','field_map'):expected[task[key]]=p['input_sha256'][task[key]]
        paths=list(dict.fromkeys([control,binary,support,triangles,projection,source_config,*map(Path,expected),Path(__file__).resolve()]))
        status('waiting_for_sixteen_shared_CPU_slots')
        with lease(16,8,deadline):
            status('hashing_complete_original_operator_sources')
            with ThreadPoolExecutor(max_workers=16) as pool:pins=dict(zip(map(str,paths),pool.map(sha,paths)))
            if any(pins[path]!=digest for path,digest in expected.items()):raise ValueError('negative support/source identity changed')
            save(output/'input_manifest.json',dict(input_sha256=pins))
            cfg,report=output/'config.json',output/'report.json'
            save(cfg,dict(support_triangles=str(triangles),shards=source['shards'],
                 global_fields=source['geometry']['global_fields'],expected_operators=p['operators'],
                 threads=16,deadline_uptime=deadline,output=str(scratch/'tasks'),report=str(report)))
            status('selecting_original_operators_for_all_negative_P1_supports')
            execute([binary,cfg],output/'selection.log',deadline,8);found=json.loads(report.read_text())
            if not found['selected_operators']:raise ValueError('nonzero target C states have no source operators')
            with ThreadPoolExecutor(max_workers=16) as pool:
                if list(pool.map(sha,paths))!=list(pins.values()):raise ValueError('selector inputs changed during scan')
            retained=[cfg,report,*sorted((scratch/'tasks').glob('*.operators.jsonl')),
                      *sorted((scratch/'tasks').glob('*.offsets.bin')),*sorted((scratch/'tasks').glob('*.summary.json'))]
            with ThreadPoolExecutor(max_workers=16) as pool:artifacts=dict(zip(map(str,retained),pool.map(sha,retained)))
            save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,
                 source_projection=str(projection.parent),source_tasks=str(source_config),selected_records=str(scratch/'tasks'),
                 results=found,complete_negative_C_operator_support_trace=True,
                 projection_tasks_recomputed=False,physical_RC_qualified=False,release_qualified=False))
            status('negative_C_source_operators_and_complete_task_ids_traced',
                   selected_operators=found['selected_operators'],affected_tasks=len(found['affected_tasks']))
    except BaseException as error:
        status('stopped_without_promotion',reason=repr(error));raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True,type=Path)
    p.add_argument('--controls',required=True,type=Path);a=p.parse_args();run(a.output.resolve(),a.controls.resolve())
