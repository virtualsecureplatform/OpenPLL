"""Prepare and independently check the complete exact native zero-R voltage map."""
import argparse
from array import array
from bisect import bisect_left
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import shutil
import struct
import sys
import time
from common import ROOT,save,sha
from compiled_charge import execute
from resources import lease


def audit_map(path,constraints,count):
    graph=defaultdict(set)
    for row in constraints:
        a,b=row['global_voltage_ids']
        graph[a].add(b);graph[b].add(a)
    roots={}
    for start in graph:
        if start in roots:
            continue
        pending=[start];component=set()
        while pending:
            node=pending.pop()
            if node in component:
                continue
            component.add(node);pending.extend(graph[node]-component)
        root=min(component)
        roots.update({node:root for node in component})
    removed=sorted(n for n,r in roots.items() if n!=r)
    if sys.byteorder!='little' or array('I').itemsize!=4:
        raise ValueError('explicit LE 32-bit map audit host required')
    with path.open('rb') as stream:
        if stream.read(8)!=b'CNETDOF1' or struct.unpack('<QQ',stream.read(16))!=(count,count-len(removed)):
            raise ValueError('zero-R map header differs from independent connectivity')
        values=array('I');values.fromfile(stream,count)
        if stream.read(1):
            raise ValueError('zero-R voltage map trailing bytes')
    for old,new in enumerate(values):
        root=roots.get(old,old)
        if new!=root-bisect_left(removed,root):
            raise ValueError('unexpected voltage alias or compacted index')
    for row in constraints:
        a,b=row['global_voltage_ids']
        if values[a]!=values[b]:
            raise ValueError('native zero-R voltage equation not satisfied')
    return len(removed)


def run(core,mapping,meshes,output):
    core,mapping,meshes,out=(p.resolve() for p in (core,mapping,meshes,output))
    out.mkdir(parents=True,exist_ok=False)
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    receipts=[p/'assessment.json' for p in (core,mapping,meshes)]
    native,voltage,mesh=[json.loads(p.read_text()) for p in receipts]
    if not native['final_native_core_R_voltage_namespace_join_complete'] or not mesh['all_selected_R_tiles_compiled']:
        raise ValueError('complete native core and R mesh namespace required')
    if native['input_sha256'].get(str(receipts[1]))!=sha(receipts[1]) or native['results']['nodes_requiring_R_only_voltage_union']:
        raise ValueError('matching complete core/spatial voltage map required')
    branches=next(Path(p) for p in native['artifacts'] if p.endswith('/native_core_branches.jsonl'))
    parts=sorted(Path(p) for p in mesh['artifacts'] if p.endswith('.jsonl'))
    source=ROOT/'tools/sheet_charge/build_zero_R_voltage_map.cpp'
    compiler=Path(shutil.which('g++')).resolve()
    paths=[*receipts,branches,*parts,source,source.parent.parent/'charge_compiler/json.hpp',compiler,Path(__file__).resolve()]
    with lease(8,8,deadline):
        with ThreadPoolExecutor(max_workers=8) as pool:
            pins=dict(zip(map(str,paths),pool.map(sha,paths)))
        if pins[str(branches)]!=native['artifacts'][str(branches)] or any(pins[str(p)]!=mesh['artifacts'][str(p)] for p in parts):
            raise ValueError('native core/mesh artifact changed')
        binary=out/'build_zero_R_voltage_map'
        execute([compiler,'-std=c++20','-O3','-Wall','-Wextra','-Wpedantic',
                 '-fno-fast-math','-ffp-contract=off',source,'-o',binary],out/'build.log',deadline,8)
        controls=out/'controls';controls.mkdir()
        def zero(a,b,k):
            return dict(branch_kind='exact_zero_voltage_constraint',global_voltage_ids=[a,b],
                native_group_id='2',native_branch_pointer='branch'+str(k),
                native_resistance_float_bits=0,native_resistance_milliohm_token='0')
        fixture=[zero(1,3,1),zero(3,5,2),zero(5,1,3),dict(branch_kind='positive_native_resistor',
            global_voltage_ids=[6,7],native_resistance_float_bits=1103626240,
            native_resistance_milliohm_token='25',nominal_conductance_siemens=40)]
        def write_rows(path,rows):
            path.write_text(''.join(json.dumps(r,sort_keys=True,separators=(',',':'))+'\n' for r in rows))
        write_rows(controls/'branches.jsonl',fixture)
        def config(root,path,count,expected,zeros):
            value=dict(branches=str(path),voltage_nodes=count,expected_branches=expected,
                expected_zero_branches=zeros,voltage_map=str(root/'voltage_map.bin'),
                aliases=str(root/'aliases.jsonl'),constraints=str(root/'constraints.jsonl'),deadline_uptime=deadline)
            save(root/'config.json',value)
            return root/'config.json'
        cfg=config(controls,controls/'branches.jsonl',8,4,3)
        execute([binary,cfg],controls/'native.log',deadline,8)
        result=json.loads((controls/'native.log').read_text())
        assert result['independent_zero_voltage_equations']==2 and result['redundant_zero_voltage_equations']==1
        assert audit_map(controls/'voltage_map.bin',fixture[:3],8)==2
        invalid=controls/'invalid';invalid.mkdir()
        write_rows(invalid/'branches.jsonl',[zero(0,1,1)])
        cfg=config(invalid,invalid/'branches.jsonl',8,1,1)
        try:
            execute([binary,cfg],invalid/'native.log',deadline,8)
        except RuntimeError:
            pass
        else:
            raise ValueError('implicit ground/reference zero-R alias accepted')
        cfg=config(out,branches,voltage['voltage_nodes'],native['results']['native_core_branches'],
                   native['results']['exact_zero_voltage_branches'])
        execute([binary,cfg],out/'native.log',deadline,8)
        constraints=[json.loads(line) for line in (out/'constraints.jsonl').read_text().splitlines()]
        independent={}
        # Re-read zero equations from every controlled native mesh, independently
        # of the core branch traversal used to construct the voltage union.
        for part in parts:
            with part.open('rb') as stream:
                for line in stream:
                    if b'"kind":"zero_R_symbolic_ends"' not in line:
                        continue
                    row=json.loads(line)
                    for c in row['auxiliary']['constraints']:
                        key=(row['native_group_id'],c['native_branch'])
                        if key in independent or c['voltage_rhs']!=0:
                            raise ValueError('ambiguous or nonzero native mesh voltage equation')
                        independent[key]=tuple(sorted((c['positive'],c['negative'])))
        from_core={(r['native_group_id'],r['native_branch_pointer']):tuple(sorted(r['private_endpoints'])) for r in constraints}
        if from_core!=independent:
            raise ValueError('complete native core and mesh zero-R equations differ')
        rank=audit_map(out/'voltage_map.bin',constraints,voltage['voltage_nodes'])
        result=json.loads((out/'native.log').read_text())
        if rank!=result['independent_zero_voltage_equations']:
            raise ValueError('independent zero-R equation rank mismatch')
        with ThreadPoolExecutor(max_workers=8) as pool:
            if list(pool.map(sha,paths))!=list(pins.values()):
                raise ValueError('zero-R map source changed')
        products=[binary,out/'voltage_map.bin',out/'aliases.jsonl',out/'constraints.jsonl',out/'native.log',
                  *[p for p in controls.rglob('*') if p.is_file()]]
        save(out/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in products},results=result,
             exact_zero_R_voltage_map_prepared=True,every_original_voltage_slot_independently_checked=True,
             every_native_core_and_mesh_zero_voltage_equation_matched=True,
             cycle_transitivity_reference_rejection_controls_pass=True,
             source_projection_assessment_pending=True,substrate_reference_fold_applied=False,
             scalar_rounding_spatial_assignment_complete=False,physical_RC_qualified=False,
             runtime_model_eligible=False,release_qualified=False))
        print(json.dumps(result))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('core','mapping','meshes','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    a=parser.parse_args()
    run(a.core,a.mapping,a.meshes,a.output)
