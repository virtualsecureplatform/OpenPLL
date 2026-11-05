"""Enclose complete original diagonal integrals after the exact support selector finishes."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from fractions import Fraction as Q
import json
import os
from pathlib import Path
import time
from common import ROOT,save,sha,verify
from compiled_charge import execute
from resources import identity,lease
from test_fringe_interval import endpoint


def run(output,selection,controls):
    output.mkdir(parents=True,exist_ok=False);parent=json.loads((selection/'owner.json').read_text())
    wait_deadline=parent['deadline_uptime']+60
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),producer_pid=parent['pid'],
         producer_birth=parent['birth'],wait_deadline_uptime=wait_deadline,cpu_slots=16,memory_GiB=32,automatic_identical_retry=False))
    def status(state,**more):save(output/'status.json',dict(state=state,release_qualified=False,**more))
    try:
        while not (selection/'assessment.json').exists():
            if identity(parent['pid'])!=parent['birth'] or time.clock_gettime(time.CLOCK_BOOTTIME)>=wait_deadline:
                raise RuntimeError('selected-source producer terminal without complete assessment')
            status('waiting_for_exact_support_selection',producer_pid=parent['pid']);time.sleep(2)
        deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
        control=controls/'assessment.json';c=json.loads(control.read_text());verify(c['input_sha256'])
        binary=controls/'enclose_selected_C_diagonals'
        if not c['selected_C_diagonal_enclosure_controls_pass'] or sha(binary)!=c['artifacts'][str(binary)]:
            raise ValueError('controlled analytic diagonal evaluator required')
        selected=selection/'assessment.json';s=json.loads(selected.read_text())
        if not s['complete_negative_C_operator_support_trace']:raise ValueError('complete selected source trace required')
        source_config=Path(s['source_tasks']);source=json.loads(source_config.read_text())
        projection=Path(s['source_projection'])/'assessment.json';p=json.loads(projection.read_text())
        targets_receipt=ROOT/'build/signoff400/startup_timing_negative_C_fields_002/assessment.json'
        t=json.loads(targets_receipt.read_text());targets=Path(t['targets'])
        tasks=[];expected={str(targets):t['artifacts'][str(targets)]}
        for number in s['results']['affected_tasks']:
            original=source['shards'][number];folder=Path(s['selected_records'])
            records,offsets=folder/f'task_{number}.operators.jsonl',folder/f'task_{number}.offsets.bin'
            expected.update({str(path):s['artifacts'][str(path)] for path in (records,offsets)})
            tasks.append(dict(original,task=number,selected_operators=str(records),selected_offsets=str(offsets),
                              selected_count=s['results']['task_counts'][number]['selected_operators']))
        for original in source['shards']:
            for key in ('operators','field_map'):expected[original[key]]=p['input_sha256'][original[key]]
        geometry=source['geometry']
        for key in ('R_index','R_bundles','template_aliases','templates'):
            expected[geometry[key]]=p['input_sha256'][geometry[key]]
        for key in ('R_parts','floating_parts'):
            for path in geometry[key]:expected[path]=p['input_sha256'][path]
        paths=list(dict.fromkeys([selected,control,binary,source_config,projection,targets_receipt,targets,
                                 *map(Path,expected),Path(__file__).resolve(),Path(__file__).with_name('test_fringe_interval.py')]))
        os.environ.update(OMP_NUM_THREADS='16',OMP_THREAD_LIMIT='16',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
        status('waiting_for_sixteen_CPU_32GiB_enclosure_lease')
        with lease(16,32,deadline):
            status('hashing_complete_selected_source_and_geometry_lineage')
            with ThreadPoolExecutor(max_workers=16) as pool:pins=dict(zip(map(str,paths),pool.map(sha,paths)))
            if any(pins[path]!=digest for path,digest in expected.items()):raise ValueError('selected integration inputs changed')
            save(output/'input_manifest.json',dict(input_sha256=pins))
            geometry=dict(geometry,deadline_uptime=deadline);results=[]
            for bits in (128,256,512,1024):
                cfg,report=output/f'{bits}.json',output/f'{bits}.report.json'
                save(cfg,dict(geometry=geometry,targets=str(targets),tasks=tasks,expected_voltage_nodes=p['global_voltage_nodes'],
                     expected_selected_operators=s['results']['selected_operators'],precision_bits=bits,threads=16,
                     deadline_uptime=deadline,report=str(report)))
                status('analytically_enclosing_every_selected_negative_diagonal',precision_bits=bits)
                execute([binary,cfg],output/f'{bits}.log',deadline,32);result=json.loads(report.read_text())
                narrow=True
                for row in result['rows']:
                    low,high=endpoint(row['interval']['lower_dyadic']),endpoint(row['interval']['upper_dyadic'])
                    old=Q(row['stored_conservative_diagonal_exact']);threshold=min(Q(1e-8),abs(old))/8
                    row['width_within_one_eighth_stored_defect']=high-low<=threshold;narrow &= high-low<=threshold
                results.append(dict(precision_bits=bits,report=str(report),all_enclosures_narrow_enough=narrow,
                    strictly_negative=result['strictly_negative_enclosures'],strictly_positive=result['strictly_positive_enclosures'],
                    exact_zero=result['exact_zero_enclosures'],encloses_zero=result['enclosures_containing_zero']))
                save(output/f'{bits}.analysis.json',result)
                if narrow:break
            with ThreadPoolExecutor(max_workers=16) as pool:
                if list(pool.map(sha,paths))!=list(pins.values()):raise ValueError('selected diagonal inputs changed')
            artifacts={str(path):sha(path) for path in output.iterdir() if path.is_file() and path.name not in ('owner.json','status.json')}
            save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,precision_results=results,
                 complete_selected_analytic_diagonal_enclosures=True,all_enclosures_narrow_enough=results[-1]['all_enclosures_narrow_enough'],
                 full_matrix_passivity_verified=False,physical_RC_qualified=False,release_qualified=False))
            status('analytic_negative_diagonal_enclosures_complete',precision_results=results)
    except BaseException as error:
        status('stopped_without_promotion',reason=repr(error));raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True,type=Path)
    p.add_argument('--selection',required=True,type=Path);p.add_argument('--controls',required=True,type=Path)
    a=p.parse_args();run(a.output.resolve(),a.selection.resolve(),a.controls.resolve())
