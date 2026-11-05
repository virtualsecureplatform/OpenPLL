#!/usr/bin/env python3
"""Validate explicit native-node aliases on observed branch subrectangles.

The area operators have synthetic unit density. This checks registration and
mathematics, not real C attachment, full tile coverage, R units or snapshots.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import time
from common import save,sha
from resources import lease
from native_axis_basis import axis_template,exact_axis_mass
from compiled_sheet_charge_registered import build,invoke,payload,decode

def run(registration,output):
    registration,out=(Path(p).resolve() for p in (registration,output));out.mkdir(parents=True,exist_ok=False);start=time.clock_gettime(time.CLOCK_BOOTTIME);deadline=start+43200
    def status(state,**extra):save(out/'status.json',dict(state=state,release_qualified=False,elapsed_s=time.clock_gettime(time.CLOCK_BOOTTIME)-start,**extra))
    save(out/'owner.json',dict(wall_limit_s=43200,automatic_identical_retry=False,cpu_slots=8,memory_limit_GiB=8))
    try:
        with lease(8,8,deadline):
            report=json.loads((registration/'assessment.json').read_text())
            if not report['all_native_branch_records_emitted'] or not report['all_wire_creation_records_emitted']:raise ValueError('complete registration records required')
            source=registration/'native/wire_creation_records.jsonl';pins={str(source):report['artifacts'][str(source)]}
            for p in (Path(__file__).resolve(),*[Path(__file__).with_name(n) for n in ('native_axis_basis.py','compiled_sheet_charge_registered.py','common.py','resources.py')],registration/'assessment.json'):pins[str(p)]=sha(p)
            for p,h in pins.items():
                if sha(p)!=h:raise ValueError('native alias input changed')
            status('selecting_observed_branch_subrectangle_controls');selected=[];seen=Counter();cases=[];expected={};scanned=0
            with source.open() as f:
                for line in f:
                    scanned+=1
                    if scanned>200000:break
                    row=json.loads(line);axis=row['flow_axis']
                    if axis not in (0,1) or row['split_tile'] or not row['creation_axis_inside_tile'] or not row['creation_axis_increasing'] or row['native_resistance_value']==0:continue
                    key=(row['raw_material'],axis)
                    if seen[key]:continue
                    box=list(row['creation_tile_internal']);a,b=row['creation_points_internal'];box[axis]=a[axis];box[axis+2]=b[axis]
                    if box[0]>=box[2] or box[1]>=box[3]:continue
                    knots=[(a[axis],row['creation_private_ids'][0]),(b[axis],row['creation_private_ids'][1])];template=axis_template(box,axis,knots);name=str(len(cases))
                    cases.append(dict(id=name,operator=['A',1,0,1,box,1.],source_basis=payload(template,'',point_nodes=template['point_nodes']),target_basis=dict(constant='REF')));expected[name]=exact_axis_mass(box,axis,knots)
                    selected.append(dict(native_record=row,restricted_strip_box_internal=box,synthetic_unit_density_operator=True,full_creation_tile_coverage=box==row['creation_tile_internal']));seen[key]+=1
                    if len(cases)>=24:break
            if not cases:raise ValueError('no observed branch control candidates')
            save(out/'selected_branches.json',selected);save(out/'input_manifest.json',dict(input_sha256=pins));binary=build(out/'build',deadline);bp=json.loads((out/'build/build.json').read_text());pins.update(bp['input_sha256']);pins.update(bp['artifacts']);status('checking_registered_private_node_mass_matrices',cases=len(cases))
            checked=0
            for threads in (1,8):
                matrices,_=invoke(binary,cases,out/('threads_'+str(threads)),threads=threads,deadline=deadline)
                for row in matrices:
                    if decode(row,exact=True)!=expected[row['id']]:raise ValueError('observed native alias matrix differs from analytic axis mass')
                    checked+=1
            for p,h in pins.items():
                if sha(p)!=h:raise ValueError('native alias input changed during control')
            result=dict(input_sha256=pins,artifacts={str(p):sha(p) for p in (out/'selected_branches.json',out/'build/build.json',out/'threads_1/matrices.jsonl',out/'threads_8/matrices.jsonl')},observed_branch_cases=len(cases),exact_matrix_comparisons=checked,materials_axes=[list(k) for k in seen],scanned_creation_records=scanned,synthetic_unit_density_operators=True,source_geometry_restricted_to_branch_subrectangle=True,full_layout_C_attachment_qualified=False,full_tile_coverage_qualified=False,snapshot_selection_qualified=False,contact_impedance_qualified=False,zero_resistance_model_qualified=False,resistance_units_and_PVT_qualified=False,physical_domain_complete=False,runtime_model_eligible=False,release_qualified=False,elapsed_s=time.clock_gettime(time.CLOCK_BOOTTIME)-start)
            save(out/'assessment.json',result);status('observed_native_alias_controls_complete_pending_physical_registration');return result
    except BaseException as e:status('failed',reason=repr(e));raise
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--registration',required=True,type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args();r=run(a.registration,a.output);print(json.dumps({k:r[k] for k in ('observed_branch_cases','exact_matrix_comparisons','elapsed_s')}))
