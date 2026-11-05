"""Prove complete source rows selected by a candidate-bound exact row-norm inventory."""
import argparse
from array import array
from fractions import Fraction
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import re
import struct
import sys
import tempfile
import time
from common import ROOT,save,sha,verify
from compiled_charge import execute
from resources import identity,lease


def trace_targets(negative_rows, exponent, compact, nodes, index, bundles, global_fields):
    """Join compacted states to native names and then to physical field bundles."""
    if not negative_rows:raise ValueError('nonempty negative witness list required')
    if sys.byteorder!='little':raise ValueError('little-endian namespace required')
    with compact.open('rb') as stream:
        header=stream.read(24)
        if header[:8]!=b'CNETDOF1':raise ValueError('compacting map format')
        original,constrained=struct.unpack('<QQ',header[8:]);values=array('I');values.fromfile(stream,original)
        if stream.read(1):raise ValueError('compacting map trailing bytes')
    targets={}
    for row,energy in negative_rows:
        if type(row) is not int or not 0<row<constrained or row in targets or not isinstance(energy,str):
            raise ValueError('unique non-reference states with exact stored diagonal integers required')
        targets[row]=dict(row=row,energy_integer=str(energy),original_voltage_nodes=[])
    wanted={old:new for old,new in enumerate(values) if new in targets}
    missing=set(wanted);groups=set()
    with nodes.open() as stream:
        for line in stream:
            i=int(line[1:line.index(',')])
            if i not in missing:continue
            found,name=json.loads(line)
            match=re.fullmatch(r'(?:_rmesh_(?:axis_end_|sheet_)?|_zero_R_)(\d+)_.+',name)
            if found!=i or not match:raise ValueError('unresolved physical voltage namespace')
            group=int(match[1]);groups.add(group)
            targets[wanted[i]]['original_voltage_nodes'].append(dict(node=i,name=name,native_group=group))
            missing.remove(i)
            if not missing:break
    if missing or any(not row['original_voltage_nodes'] for row in targets.values()):
        raise ValueError('incomplete inverse voltage namespace')
    raw=index.read_bytes()
    if raw[:8]!=b'RBSIDX01' or struct.unpack_from('<Q',raw,8)[0]!=global_fields or len(raw)!=16+16*global_fields:
        raise ValueError('R field index namespace')
    field_by_bundle={}
    for field in range(1,global_fields):
        start,_,bundle=struct.unpack_from('<QII',raw,16+16*field)
        if start!=2**64-1:
            if bundle in field_by_bundle:raise ValueError('ambiguous R bundle field')
            field_by_bundle[bundle]=field
    fields={group:set() for group in groups}
    with bundles.open() as stream:
        for line in stream:
            b=json.loads(line);field=field_by_bundle[b['bundle_id']]
            for ref in b['tile_references']:
                group=int(ref[2])
                if group in fields:fields[group].add(field)
    if any(not f for f in fields.values()):raise ValueError('native group has no physical fields')
    for row in targets.values():
        for node in row['original_voltage_nodes']:node['candidate_global_fields']=sorted(fields[node['native_group']])
    return dict(schema_version=1,negative_nodes=list(targets.values()),global_fields=sorted(set.union(*fields.values())),
                energy_binary_quantum_exponent=exponent,targeted_recompute_coverage_certified=False,
                physical_RC_qualified=False,release_qualified=False)


def run(candidate,output,support_controls,selector_controls,symbolic_controls,inventory):
    output.mkdir(parents=True,exist_ok=False);parent=json.loads((candidate/'owner.json').read_text())
    waiting=parent['deadline_uptime']+60
    save(output/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid()),producer_pid=parent['pid'],
         producer_birth=parent['birth'],wait_deadline_uptime=waiting,cpu_slots=16,memory_GiB=32,automatic_identical_retry=False))
    scratch=Path(tempfile.mkdtemp(prefix='openpll-zero-C-followup-',dir='/tmp'));(output/'native').symlink_to(scratch,target_is_directory=True)
    def status(state,**more):save(output/'status.json',dict(state=state,release_qualified=False,**more))
    try:
        while not (candidate/'assessment.json').exists():
            if identity(parent['pid'])!=parent['birth'] or time.clock_gettime(time.CLOCK_BOOTTIME)>=waiting:
                raise RuntimeError('candidate producer terminal without certified derivative')
            status('waiting_for_exact_candidate_derivative',producer_pid=parent['pid']);time.sleep(2)
        deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
        assessment=candidate/'assessment.json';a=json.loads(assessment.read_text());result=a['results']
        if not a['conservative_C_stored_coefficient_derivative_certified'] or not result['all_corrections_within_existing_coefficient_tolerance']:
            raise ValueError('certified candidate derivative required')
        inventory_receipt=inventory/'assessment.json';candidates=inventory/'candidates.json'
        inv=json.loads(inventory_receipt.read_text());verify(inv['artifacts'])
        rows=json.loads(candidates.read_text())
        operator_path=Path(a['logical_operator_manifest'])
        if (inv.get('all_exact_row_norms_inventoried') is not True
                or inv['input_sha256'].get(str(operator_path))!=a['artifacts'][str(operator_path)]
                or rows['coefficient_quantum_exponent']!=result['common_binary_quantum_exponent']
                or rows['selection_threshold_raw']!='1e-8'
                or inv['selected_rows']!=len(rows['rows'])):
            raise ValueError('complete candidate-matching small-row inventory required')
        quantum=Fraction(2)**rows['coefficient_quantum_exponent'];selected={}
        for row in rows['rows']:
            i=row['row'];energy=row['diagonal_integer'];l1=int(row['original_L1_integer'])
            if type(i) is not int or i<=0 or i in selected or l1<=0 or l1*quantum>Fraction(1,100000000) or abs(int(energy)*quantum)>Fraction(1,100000000):
                raise ValueError('invalid exact small-row candidate')
            selected[i]=energy
        negative=sorted(selected.items())
        if not negative:raise ValueError('no small-row candidates to prove')
        proof_specs=[(support_controls,'extract_negative_C_support','negative_C_P1_support_controls_pass'),
                     (selector_controls,'select_negative_C_operators','negative_C_operator_selector_controls_pass'),
                     (symbolic_controls,'prove_selected_C_zero_rows','exact_symbolic_C_zero_row_controls_pass')]
        binaries=[];control_paths=[]
        for folder,name,flag in proof_specs:
            receipt=folder/'assessment.json';c=json.loads(receipt.read_text());verify(c['input_sha256']);binary=folder/name
            if c.get(flag) is not True or sha(binary)!=c['artifacts'][str(binary)]:raise ValueError('controlled followup component required: '+name)
            binaries.append(binary);control_paths.extend([receipt,binary])
        base=ROOT/'build/signoff400';projection=base/'startup_timing_full_spatial_projection_002/assessment.json'
        p=json.loads(projection.read_text());source_config=projection.parent/'config.json';source=json.loads(source_config.read_text());geometry=source['geometry']
        op_path=Path(a['logical_operator_manifest']);op=json.loads(op_path.read_text());existing_mask=Path(op['zero_rows']['path'])
        for path in (op_path,existing_mask):
            if sha(path)!=a['artifacts'][str(path)]:raise ValueError('candidate operator/mask changed')
        mask=existing_mask.read_bytes()
        if any(mask[16+row] for row,_ in negative):raise ValueError('negative diagonal conflicts with an already-proved zero row')
        compact=base/'startup_timing_zero_R_voltage_map_002/voltage_map.bin'
        nodes=Path('/tmp/openpll-spatial-charge-3g9ks0nr/native/R_nodes.jsonl')
        expected={str(compact):a['input_sha256'][str(compact)],str(nodes):p['artifacts'][str(nodes)]}
        for key in ('R_index','R_bundles','template_aliases','templates'):
            expected[geometry[key]]=p['input_sha256'][geometry[key]]
        for key in ('R_parts','floating_parts'):
            for path in geometry[key]:expected[path]=p['input_sha256'][path]
        for shard in source['shards']:
            for key in ('operators','field_map'):expected[shard[key]]=p['input_sha256'][shard[key]]
        paths=list(dict.fromkeys([assessment,op_path,existing_mask,projection,source_config,inventory_receipt,candidates,*control_paths,
                                 *map(Path,expected),Path(__file__).resolve()]))
        os.environ.update(OMP_NUM_THREADS='16',OMP_THREAD_LIMIT='16',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
        status('waiting_for_followup_resource_lease')
        with lease(16,32,deadline):
            status('hashing_complete_followup_source_lineage')
            with ThreadPoolExecutor(max_workers=16) as pool:pins=dict(zip(map(str,paths),pool.map(sha,paths)))
            if any(pins[path]!=h for path,h in expected.items()):raise ValueError('followup source/namespace changed')
            save(output/'input_manifest.json',dict(input_sha256=pins))
            targets=output/'targets.json';save(targets,trace_targets(negative,result['common_binary_quantum_exponent'],compact,nodes,
                 Path(geometry['R_index']),Path(geometry['R_bundles']),geometry['global_fields']))
            target_data=json.loads(targets.read_text());target_data.update(selection_reason='all remaining small nonzero row norms from the complete exact row inventory',selection_threshold_raw='1e-8',threshold_used_only_to_select_proof_work=True,stored_energy_integer_is_actual_diagonal=True)
            save(targets,target_data)
            generated={str(targets):sha(targets)}
            geometry=dict(geometry,deadline_uptime=deadline)
            support_cfg,triangles,support_report=output/'support.json',output/'triangles.jsonl',output/'support.report.json'
            save(support_cfg,dict(targets=str(targets),geometry=geometry,threads=8,deadline_uptime=deadline,triangles=str(triangles),report=str(support_report)))
            generated[str(support_cfg)]=sha(support_cfg)
            status('resolving_all_followup_P1_support_triangles');execute([binaries[0],support_cfg],output/'support.log',deadline,8)
            generated.update({str(path):sha(path) for path in (triangles,support_report)})
            selector_cfg,selected_report=output/'selection.json',output/'selection.report.json'
            save(selector_cfg,dict(support_triangles=str(triangles),shards=source['shards'],global_fields=geometry['global_fields'],
                 expected_operators=p['operators'],threads=16,deadline_uptime=deadline,output=str(scratch/'tasks'),report=str(selected_report)))
            generated[str(selector_cfg)]=sha(selector_cfg)
            status('tracing_complete_source_for_followup_rows');execute([binaries[1],selector_cfg],output/'selection.log',deadline,8)
            generated[str(selected_report)]=sha(selected_report)
            selection=json.loads(selected_report.read_text());tasks=[]
            for number in selection['affected_tasks']:
                tasks.append(dict(source['shards'][number],task=number,
                    selected_operators=str(scratch/f'tasks/task_{number}.operators.jsonl'),selected_offsets=str(scratch/f'tasks/task_{number}.offsets.bin'),
                    selected_count=selection['task_counts'][number]['selected_operators']))
            selected_paths=[Path(task[key]) for task in tasks for key in ('selected_operators','selected_offsets')]
            with ThreadPoolExecutor(max_workers=16) as pool:generated.update(dict(zip(map(str,selected_paths),pool.map(sha,selected_paths))))
            config,report=output/'config.json',output/'report.json'
            save(config,dict(geometry=geometry,targets=str(targets),voltage_map=str(compact),tasks=tasks,
                 expected_voltage_nodes=p['global_voltage_nodes'],expected_selected_operators=selection['selected_operators'],
                 precision_bits=128,threads=16,deadline_uptime=deadline,report=str(report)))
            generated[str(config)]=sha(config)
            status('proving_followup_rows_by_exact_symbolic_cancellation');execute([binaries[2],config],output/'proof.log',deadline,32)
            found=json.loads(report.read_text())
            if {r['row'] for r in found['rows']}!={r for r,_ in negative} or found['target_rows']!=len(negative):
                raise ValueError('followup proof omitted or added witness rows')
            verify(generated)
            with ThreadPoolExecutor(max_workers=16) as pool:
                if list(pool.map(sha,paths))!=list(pins.values()):raise ValueError('followup proof input changed')
            retained=[targets,support_cfg,triangles,support_report,selector_cfg,selected_report,config,report,
                      *sorted((scratch/'tasks').glob('*.operators.jsonl')),*sorted((scratch/'tasks').glob('*.offsets.bin'))]
            with ThreadPoolExecutor(max_workers=16) as pool:artifacts=dict(zip(map(str,retained),pool.map(sha,retained)))
            save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,results=found,
                 complete_target_C_symbolic_row_expressions_assembled=True,
                 all_target_C_rows_exactly_zero=found['all_target_rows_exactly_zero'],
                 source_level_zero_row_certificate_complete=found['all_target_rows_exactly_zero'],
                 numerical_coefficient_threshold_used=False,matrix_modified=False,full_matrix_passivity_verified=False,
                 physical_RC_qualified=False,release_qualified=False))
            status('followup_symbolic_row_proof_complete',all_rows_exactly_zero=found['all_target_rows_exactly_zero'])
    except BaseException as error:
        status('stopped_without_promotion',reason=repr(error));raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('candidate','output','support-controls','selector-controls','symbolic-controls','inventory'):parser.add_argument('--'+name,required=True,type=Path)
    a=parser.parse_args();run(a.candidate.resolve(),a.output.resolve(),a.support_controls.resolve(),a.selector_controls.resolve(),a.symbolic_controls.resolve(),a.inventory.resolve())
