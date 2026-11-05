"""Assemble nominal single-anchor R extensions and retain unknown semiconductor ends."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from fractions import Fraction as F
import json
from pathlib import Path
import shutil
import tempfile
import time
from common import ROOT,save,sha
from compiled_charge import execute
from resources import lease
from native_anchored_sheet import prepare


def run(meshes,audit,mapping,matrix_controls,merger_upgrade,output):
    meshes,audit,mapping,matrix_controls,merger_upgrade,out=(p.resolve() for p in
        (meshes,audit,mapping,matrix_controls,merger_upgrade,output))
    out.mkdir(parents=True,exist_ok=False);scratch=Path(tempfile.mkdtemp(prefix='openpll-R-extension-G-',dir='/tmp'))
    (out/'native').symlink_to(scratch,target_is_directory=True);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    proofs=[p/'assessment.json' for p in (meshes,audit,mapping,matrix_controls,merger_upgrade)]
    mesh,checked,maps,structure,upgrade=[json.loads(p.read_text()) for p in proofs]
    if not checked['all_selected_R_meshes_independently_reconstructed'] or not checked['exact_native_and_latent_voltage_names_match']:
        raise ValueError('full independent native R mesh audit required')
    if not structure['matrix_structure_controls_pass'] or not upgrade['actual_operator_merge_bytes_identical']:
        raise ValueError('controlled matrix auditor and merger required')
    parts=sorted(Path(p) for p in mesh['artifacts'] if p.endswith('.jsonl'))
    rnodes=Path(json.loads((mapping/'config.json').read_text())['R_nodes'])
    source=ROOT/'tools/sheet_charge/compile_R_extension_G.cpp';compiler=Path(shutil.which('g++')).resolve()
    merger=Path(upgrade['merger_binary']);auditor=matrix_controls/'audit_sparse_matrix'
    helper=Path(__file__).with_name('native_anchored_sheet.py')
    paths=[*proofs,*parts,rnodes,source,source.parent/'sparse_runs_v2.hpp',ROOT/'tools/charge_compiler/json.hpp',
           compiler,merger,auditor,helper,helper.with_name('floating_sheet_basis.py'),Path(__file__).resolve()]
    def status(state,**extra):save(out/'status.json',dict(state=state,release_qualified=False,**extra))
    try:
        with lease(8,16,deadline):
            with ThreadPoolExecutor(max_workers=8) as pool:pins=dict(zip(map(str,paths),pool.map(sha,paths)))
            for p in parts:
                if pins[str(p)]!=mesh['artifacts'][str(p)] or pins[str(p)]!=checked['runtime_part_sha256'][str(p)]:
                    raise ValueError('independently audited R mesh changed')
            if pins[str(rnodes)]!=maps['input_sha256'][str(rnodes)] or pins[str(merger)]!=upgrade['input_sha256'][str(merger)] or pins[str(auditor)]!=structure['artifacts'][str(auditor)]:
                raise ValueError('R extension namespace/numeric binary changed')
            binary=out/'compile_R_extension_G'
            execute([compiler,'-std=c++20','-O3','-fopenmp','-Wall','-Wextra','-Wpedantic','-fno-fast-math',
                 '-ffp-contract=off',source,'-lgmpxx','-lgmp','-o',binary],out/'build.log',deadline,8)
            artifacts={}
            def merge(current,root,label,want_json=False):
                level=0
                while len(current)>1 or (want_json and level==0):
                    after=[]
                    for start in range(0,len(current),128):
                        cfg=root/f'{label}_{level}_{start}.json';result=root/f'{label}_{level}_{start}.bin'
                        settings=dict(inputs=list(map(str,current[start:start+128])),output=str(result),deadline_uptime=deadline)
                        if want_json:settings['json_output']=str(root/(label+'.jsonl'))
                        save(cfg,settings);execute([merger,cfg],root/f'{label}_{level}_{start}.log',deadline,2)
                        artifacts[str(result)]=sha(result);after.append(result)
                    current=after;level+=1
                return current[0]
            control=out/'controls';control.mkdir()
            native='_rmesh_2_1';namespace='_rmesh_sheet_2_7:r1'
            model=prepare([0,0,2,2],[([1,1],native)],namespace,1)
            template=model['template']
            anchor=dict(native_group_id='2',tile_serial=7,box=[0,0,2,2],
                points=[[int(x),int(y)] for x,y in template['points']],point_nodes=template['point_nodes'],
                triangles=template['triangles'],auxiliary=dict(kind='anchored_sheet',nominal_sheet_milliohms_per_square='1000'))
            end='_rmesh_axis_end_2_8_hi'
            axis=dict(native_group_id='2',tile_serial=8,auxiliary=dict(kind='nominal_axis_ends',stubs=[dict(
                endpoint_nodes=[native,end],new_latent_node=end,nominal_resistance_milliohms_exact=['25','1'])]))
            znames=['_zero_R_2_9:lo',native,'_rmesh_2_2','_rmesh_2_3','_zero_R_2_9:hi']
            zero=dict(native_group_id='2',tile_serial=9,box=[0,0,4,2],
                points=[[x,y] for x in range(5) for y in (0,2)],point_nodes=[n for n in znames for _ in range(2)],
                auxiliary=dict(kind='zero_R_symbolic_ends',raw_material='ndiode',constraints=[{},{}]))
            names=list(dict.fromkeys([native,*template['point_nodes'],end,*znames]));ids={n:i+1 for i,n in enumerate(names)}
            (control/'R_nodes.jsonl').write_text(''.join(json.dumps([ids[n],n])+'\n' for n in names))
            fixtures=[]
            for i,row in enumerate((anchor,axis,zero)):
                p=control/f'part_{i}.jsonl';p.write_text(json.dumps(row)+'\n');fixtures.append(p)
            expected={}
            for (a,b),value in model['conductance'].items():
                i,j=ids[a],ids[b]
                if i<=j and value:expected[i,j]=value
            for a,b,value in ((native,native,F(40)),(end,end,F(40)),(native,end,F(-40))):
                key=tuple(sorted((ids[a],ids[b])));expected[key]=expected.get(key,F(0))+value
            outputs=[]
            for threads in (1,4,8):
                root=control/f'threads_{threads}';root.mkdir();cfg=root/'config.json'
                save(cfg,dict(R_nodes=str(control/'R_nodes.jsonl'),R_parts=list(map(str,fixtures)),threads=threads,
                     max_accumulator_entries=16,expected_tiles=3,output=str(root/'runs'),deadline_uptime=deadline))
                execute([binary,cfg],root/'native.log',deadline,8)
                result=merge(sorted((root/'runs').glob('*.bin')),root,'G',True);outputs.append(result.read_bytes())
                actual={(a,b):F(v) for a,b,v,absolute,terms in map(json.loads,(root/'G.jsonl').read_text().splitlines())}
                assert actual==expected
                symbols=[json.loads(s) for p in (root/'runs').glob('symbolic_*.jsonl') for s in p.read_text().splitlines()]
                assert len(symbols)==2 and all(F(*map(int,s['resistance_squares_exact']))==F(1,2) and not s['finite_conductance_assigned'] for s in symbols)
            assert outputs[0]==outputs[1]==outputs[2]
            bad=dict(anchor,point_nodes=list(anchor['point_nodes']))
            bad['point_nodes'][0]='_rmesh_2_2'
            (control/'bad_part.jsonl').write_text(json.dumps(bad)+'\n')
            cfg=control/'bad.json';save(cfg,dict(R_nodes=str(control/'R_nodes.jsonl'),R_parts=[str(control/'bad_part.jsonl')],threads=1,
                 max_accumulator_entries=16,expected_tiles=1,output=str(control/'bad_runs'),deadline_uptime=deadline))
            try:execute([binary,cfg],control/'bad.log',deadline,8)
            except RuntimeError:pass
            else:raise ValueError('two native anchors would change the native DC graph')
            cfg=out/'config.json';save(cfg,dict(R_nodes=str(rnodes),R_parts=list(map(str,parts)),threads=8,
                 max_accumulator_entries=250000,expected_tiles=mesh['tiles'],output=str(scratch/'runs'),deadline_uptime=deadline))
            status('assembling_all_nominal_R_extensions')
            execute([binary,cfg],out/'native.log',deadline,16)
            summary=json.loads((out/'native.log').read_text());runs=sorted((scratch/'runs').glob('*.bin'))
            if len(runs)!=summary['sparse_runs'] or not runs:raise ValueError('complete extension G runs required')
            artifacts.update({str(p):sha(p) for p in runs});matrix=merge(runs,scratch,'G')
            symbolic=sorted((scratch/'runs').glob('symbolic_*.jsonl'))
            actual_symbols=sum(sum(1 for _ in p.open()) for p in symbolic)
            if actual_symbols!=summary['unresolved_symbolic_end_stubs']:raise ValueError('symbolic end coverage differs')
            cfg=out/'matrix_audit.json';report=out/'matrix_audit.report.json'
            save(cfg,dict(matrix=str(matrix),node_count=maps['voltage_nodes'],threads=8,maximum_dense_bytes=16*1024**3,
                 deadline_uptime=deadline,scaled_charge_residual_limit=1e-12,report=str(report)))
            status('checking_every_nominal_extension_G_row')
            execute([auditor,cfg],out/'matrix_audit.log',deadline,16)
            numeric=json.loads(report.read_text())
            if not numeric['necessary_checks_pass']:raise ValueError('extension G numerical structure failed')
            with ThreadPoolExecutor(max_workers=8) as pool:
                if list(pool.map(sha,paths))!=list(pins.values()):raise ValueError('R extension source changed')
            for p in [binary,matrix,report,out/'native.log',*symbolic,*[p for p in control.rglob('*') if p.is_file()]]:artifacts[str(p)]=sha(p)
            save(out/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,nominal_extension_G_matrix=str(matrix),
                 complete_known_nominal_R_extension_G_assembled=True,results=summary,numerical_matrix_structure=numeric,
                 exact_single_anchor_sheet_and_stub_controls_pass=True,native_DC_graph_preserved=True,
                 symbolic_semiconductor_end_models_retained_without_guessing=True,
                 source_projection_assessment_pending=True,full_spatial_G_matrix_assembled=False,
                 material_and_resistance_PVT_qualified=False,physical_RC_qualified=False,runtime_model_eligible=False,release_qualified=False))
            status('known_nominal_extension_G_assembled_symbolic_ends_unresolved',results=summary);print(json.dumps(summary))
    except BaseException as error:status('failed',reason=repr(error));raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('meshes','audit','mapping','matrix-controls','merger-upgrade','output'):parser.add_argument('--'+name,type=Path,required=True)
    a=parser.parse_args();run(a.meshes,a.audit,a.mapping,a.matrix_controls,a.merger_upgrade,a.output)
