"""Combine known G and exact zero-R constraints, retaining unresolved sheet parameters."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from fractions import Fraction as F
import json
from pathlib import Path
import shutil
import struct
import tempfile
import time
from audit_substrate_reference_binding import x87
from common import ROOT,save,sha
from compiled_charge import execute
from resources import lease


def concatenate(inputs,output):
    counts=[];previous=None
    for path in inputs:
        with path.open('rb') as stream:
            if stream.read(8)!=b'SPCRUN01':raise ValueError('sparse range magic')
            count=struct.unpack('<Q',stream.read(8))[0]
            if path.stat().st_size!=16+40*count:raise ValueError('sparse range size')
            if count:
                first=struct.unpack('<Q',stream.read(8))[0];stream.seek(-40,2);last=struct.unpack('<Q',stream.read(8))[0]
                if previous is not None and first<=previous:raise ValueError('concatenated ranges must be strictly disjoint and ordered')
                previous=last
            counts.append(count)
    with output.open('xb') as target:
        target.write(b'SPCRUN01'+struct.pack('<Q',sum(counts)))
        for path in inputs:
            with path.open('rb') as source:
                source.seek(16);shutil.copyfileobj(source,target,1024**2)
    return counts


def run(core,floating,extension,mapping,zero_map,transform_controls,matrix_controls,merger_upgrade,output):
    core,floating,extension,mapping,zero_map,transform_controls,matrix_controls,merger_upgrade,out=(p.resolve() for p in
        (core,floating,extension,mapping,zero_map,transform_controls,matrix_controls,merger_upgrade,output))
    out.mkdir(parents=True,exist_ok=False);scratch=Path(tempfile.mkdtemp(prefix='openpll-known-G-',dir='/tmp'))
    (out/'native').symlink_to(scratch,target_is_directory=True);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    proofs=[p/'assessment.json' for p in (core,floating,extension,mapping,zero_map,transform_controls,matrix_controls,merger_upgrade)]
    native,fill,extra,maps,zeros,transform,check,upgrade=[json.loads(p.read_text()) for p in proofs]
    for report,key in ((native,'complete_native_positive_core_G_assembled'),(fill,'complete_nominal_floating_sheet_G_assembled'),(extra,'complete_known_nominal_R_extension_G_assembled')):
        if not report[key] or report['input_sha256'].get(str(proofs[3]))!=sha(proofs[3]):raise ValueError('matching complete component namespaces required')
    if not zeros['every_original_voltage_slot_independently_checked'] or zeros['input_sha256'].get(str(proofs[3]))!=sha(proofs[3]):raise ValueError('matching exact zero-R map required')
    if not transform['ordered_zero_R_transform_controls_pass'] or not check['matrix_structure_controls_pass'] or not upgrade['actual_operator_merge_bytes_identical']:raise ValueError('controlled numeric tools required')
    cm=Path(native['native_core_G_matrix']);em=Path(extra['nominal_extension_G_matrix'])
    fm=next(Path(p) for p in fill['artifacts'] if p.endswith('/floating_G.bin'))
    symbolic_dir=Path(json.loads((extension/'config.json').read_text())['output'])
    symbolic=sorted(symbolic_dir.glob('symbolic_*.jsonl'))
    zero_file,aliases=(zero_map/name for name in ('voltage_map.bin','aliases.jsonl'))
    merger=Path(upgrade['merger_binary']);collapse=transform_controls/'collapse_zero_R_matrix';auditor=matrix_controls/'audit_sparse_matrix'
    source=ROOT/'tools/sheet_charge/compile_symbolic_end_G.cpp';compiler=Path(shutil.which('g++')).resolve()
    expected={str(cm):native['artifacts'][str(cm)],str(em):extra['artifacts'][str(em)],str(fm):fill['artifacts'][str(fm)],
        str(merger):upgrade['input_sha256'][str(merger)],str(collapse):transform['artifacts'][str(collapse)],str(auditor):check['artifacts'][str(auditor)],
        **{str(p):extra['artifacts'][str(p)] for p in symbolic},**{str(p):zeros['artifacts'][str(p)] for p in (zero_file,aliases)}}
    paths=[*proofs,*map(Path,expected),source,source.parent/'sparse_runs_v2.hpp',ROOT/'tools/charge_compiler/json.hpp',
           compiler,Path(__file__).resolve(),Path(__file__).with_name('audit_substrate_reference_binding.py')]
    def status(state,**extra):save(out/'status.json',dict(state=state,release_qualified=False,**extra))
    try:
        with lease(8,16,deadline):
            with ThreadPoolExecutor(max_workers=8) as pool:pins=dict(zip(map(str,paths),pool.map(sha,paths)))
            if any(pins[p]!=h for p,h in expected.items()):raise ValueError('known G component or tool changed')
            binary=out/'compile_symbolic_end_G'
            execute([compiler,'-std=c++20','-O3','-Wall','-Wextra','-Wpedantic','-fno-fast-math','-ffp-contract=off',
                     source,'-lgmpxx','-lgmp','-o',binary],out/'build.log',deadline,8)
            controls=out/'controls';controls.mkdir()
            sample=[dict(finite_conductance_assigned=False,requires_sheet_model_for_material='test',global_voltage_ids=[end,1],
                    private_endpoints=[f'_zero_R_2_9:{end}','_rmesh_2_1'],resistance_squares_exact=square)
                    for end,square in ((2,['1','2']),(3,['2','3']))]
            (controls/'ends.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in sample))
            cfg=controls/'config.json';save(cfg,dict(voltage_nodes=4,symbolic_parts=[str(controls/'ends.jsonl')],
                 expected_symbolic_ends=2,output=str(controls/'unit'),deadline_uptime=deadline))
            execute([binary,cfg],controls/'native.log',deadline,8)
            data=(controls/'unit/test.unit_square_G.bin').read_bytes();actual={}
            for offset in range(16,len(data),40):
                key=struct.unpack_from('<Q',data,offset)[0];actual[key>>32,key&0xffffffff]=x87(data[offset+8:offset+18])
            assert actual=={(1,1):F(7,2),(1,2):F(-2),(1,3):F(-3,2),(2,2):F(2),(3,3):F(3,2)}
            bad=[dict(sample[0],finite_conductance_assigned=True)]
            (controls/'bad.jsonl').write_text(json.dumps(bad[0])+'\n')
            cfg=controls/'bad.json';save(cfg,dict(voltage_nodes=4,symbolic_parts=[str(controls/'bad.jsonl')],
                 expected_symbolic_ends=1,output=str(controls/'bad_unit'),deadline_uptime=deadline))
            try:execute([binary,cfg],controls/'bad.log',deadline,8)
            except RuntimeError:pass
            else:raise ValueError('preassigned numeric law accepted as unresolved')
            cfg=out/'symbolic.json';save(cfg,dict(voltage_nodes=maps['voltage_nodes'],symbolic_parts=list(map(str,symbolic)),
                 expected_symbolic_ends=extra['results']['unresolved_symbolic_end_stubs'],output=str(scratch/'symbolic'),deadline_uptime=deadline))
            execute([binary,cfg],out/'symbolic.log',deadline,8)
            family=json.loads((out/'symbolic.log').read_text())
            status('merging_overlapping_known_native_and_extension_G')
            prefix=scratch/'known_R_G.bin';cfg=out/'merge_prefix.json'
            save(cfg,dict(inputs=[str(cm),str(em)],output=str(prefix),deadline_uptime=deadline))
            execute([merger,cfg],out/'merge_prefix.log',deadline,2)
            known=scratch/'known_G.bin';counts=concatenate([prefix,fm],known)
            artifacts={str(p):sha(p) for p in (prefix,known)}
            def constrain(matrix,label):
                cfg=out/(label+'.transform.json');runs=scratch/(label+'_runs')
                save(cfg,dict(matrix=str(matrix),voltage_map=str(zero_file),aliases=str(aliases),max_accumulator_entries=1000000,
                     output=str(runs),deadline_uptime=deadline))
                execute([collapse,cfg],out/(label+'.transform.log'),deadline,8)
                current=sorted(runs.glob('*.bin'));level=0
                while len(current)>1:
                    after=[]
                    for start in range(0,len(current),128):
                        cfg=scratch/f'{label}_{level}_{start}.json';result=scratch/f'{label}_{level}_{start}.bin'
                        save(cfg,dict(inputs=list(map(str,current[start:start+128])),output=str(result),deadline_uptime=deadline))
                        execute([merger,cfg],scratch/f'{label}_{level}_{start}.log',deadline,2);after.append(result)
                    current=after;level+=1
                if not current:raise ValueError('complete constrained G required')
                artifacts[str(current[0])]=sha(current[0]);return current[0]
            status('applying_exact_native_zero_R_constraints_to_known_G')
            conditioned=constrain(known,'known')
            for member in family['material_families']:
                unit=Path(member['unit_square_matrix']);artifacts[str(unit)]=sha(unit)
                member['zero_R_constrained_unit_square_matrix']=str(constrain(unit,'unit_'+member['material']))
            cfg=out/'matrix_audit.json';report=out/'matrix_audit.report.json'
            save(cfg,dict(matrix=str(conditioned),node_count=zeros['results']['constrained_voltage_nodes'],threads=8,
                 maximum_dense_bytes=16*1024**3,deadline_uptime=deadline,scaled_charge_residual_limit=1e-12,report=str(report)))
            status('checking_every_combined_known_G_row')
            execute([auditor,cfg],out/'matrix_audit.log',deadline,16)
            numeric=json.loads(report.read_text())
            if not numeric['necessary_checks_pass']:raise ValueError('combined constrained known G structure failed')
            with ThreadPoolExecutor(max_workers=8) as pool:
                if list(pool.map(sha,paths))!=list(pins.values()):raise ValueError('combined G source changed')
            for p in [binary,report,out/'symbolic.log',*[p for p in controls.rglob('*') if p.is_file()]]:artifacts[str(p)]=sha(p)
            save(out/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,
                 combined_known_nominal_G_assembled=True,known_G_matrix=str(known),zero_R_constrained_known_G_matrix=str(conditioned),
                 native_and_floating_range_entry_counts=counts,symbolic_material_families=family,
                 exact_symbolic_fixture_and_no_numeric_default_controls_pass=True,numerical_matrix_structure=numeric,
                 native_zero_R_constraints_applied=True,source_projection_assessment_pending=True,
                 symbolic_material_values_selected=False,full_numeric_spatial_G_matrix_assembled=False,
                 material_and_resistance_PVT_qualified=False,physical_RC_qualified=False,runtime_model_eligible=False,release_qualified=False))
            status('known_G_combined_exact_zero_R_applied_symbolic_laws_unresolved');print(json.dumps(dict(known_G_combined=True,
                 upper_entries=numeric['upper_entries'],unresolved_ends=family['symbolic_end_stubs'])))
    except BaseException as error:status('failed',reason=repr(error));raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('core','floating','extension','mapping','zero-map','transform-controls','matrix-controls','merger-upgrade','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    a=parser.parse_args();run(a.core,a.floating,a.extension,a.mapping,a.zero_map,a.transform_controls,a.matrix_controls,a.merger_upgrade,a.output)
