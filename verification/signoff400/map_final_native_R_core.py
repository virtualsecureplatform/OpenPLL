"""Bind unchanged final native core resistors to the spatial voltage namespace."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import shutil
import tempfile
import time
from common import ROOT,save,sha
from compiled_charge import execute
from resources import lease


def run(extraction,snapshot,mapping,output):
    extraction,snapshot,mapping,out=(p.resolve() for p in (extraction,snapshot,mapping,output))
    out.mkdir(parents=True,exist_ok=False)
    scratch=Path(tempfile.mkdtemp(prefix='openpll-native-R-core-',dir='/tmp'))
    (out/'native').symlink_to(scratch,target_is_directory=True)
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    index=(extraction/'domain_index').resolve()
    domain=(extraction/'domain').resolve()
    receipts=[index/'assessment.json',snapshot/'assessment.json',mapping/'assessment.json',domain/'assessment.json']
    idx,snap,maps,dom=[json.loads(p.read_text()) for p in receipts]
    if not snap['final_res_ext_node_and_resistor_multisets_match']:
        raise ValueError('complete final native R snapshot proof required')
    for r in (idx,snap):
        if r['input_sha256'].get(str(receipts[3]))!=sha(receipts[3]):
            raise ValueError('native core index/snapshot/domain identity differs')
    selected=snapshot/'native_result.json'
    provenance=domain/'trace/R_provenance.log'
    nodes=index/'nodes.json'
    rnodes=Path(json.loads((mapping/'config.json').read_text())['R_nodes'])
    expected={str(selected):snap['artifacts'][str(selected)],str(provenance):snap['input_sha256'][str(provenance)],
              str(nodes):idx['artifacts'][str(nodes)],str(rnodes):maps['input_sha256'][str(rnodes)]}
    source=ROOT/'tools/sheet_charge/map_native_R_core.cpp'
    compiler=Path(shutil.which('g++')).resolve()
    paths=[*receipts,*map(Path,expected),source,source.parent.parent/'charge_compiler/json.hpp',compiler,Path(__file__).resolve()]
    def status(state,**extra):
        save(out/'status.json',dict(state=state,retained_local_scratch=str(scratch),release_qualified=False,**extra))
    try:
        with lease(8,16,deadline):
            with ThreadPoolExecutor(max_workers=8) as pool:
                pins=dict(zip(map(str,paths),pool.map(sha,paths)))
            if any(pins[p]!=h for p,h in expected.items()):
                raise ValueError('native core input changed')
            binary=out/'map_native_R_core'
            execute([compiler,'-std=c++20','-O3','-Wall','-Wextra','-Wpedantic',
                     '-fno-fast-math','-ffp-contract=off',source,'-o',binary],out/'build.log',deadline,8)
            controls=out/'controls'
            controls.mkdir()
            save(controls/'selected.json',dict(selected_groups=[dict(group=2,original='netA')]))
            save(controls/'nodes.json',[dict(native_group_id='2',original_conductor='netA',
                native_pointer=p,private_id=f'_rmesh_2_{i}',printed_name=n,point_internal=[i,7])
                for i,p,n in ((11,'0xa','netA'),(12,'0xb','netA.n0'))])
            (controls/'R_nodes.jsonl').write_text('[1,"_rmesh_2_11"]\n[2,"_rmesh_2_12"]\n')
            (controls/'provenance.log').write_text('BEGIN 1 "old"\nEND 1\nBEGIN 2 "netA"\n'
                'NODE 2 0xa "netA" 11 7 0 0\nNODE 2 0xb "netA.n0" 12 7 0 0\n'
                'BRANCH 2 0xt 0xr\nEDGE 2 0xt 0xa 0xb 25 44 0\n'
                'BRANCH 2 0xt 0xz\nEDGE 2 0xt 0xa 0xb 0 47 0\nEND 2\n')
            cfg=dict(selected_groups=str(controls/'selected.json'),nodes=str(controls/'nodes.json'),
                 R_nodes=str(controls/'R_nodes.jsonl'),provenance=str(controls/'provenance.log'),
                 node_output=str(controls/'mapped_nodes.jsonl'),edge_output=str(controls/'mapped_edges.jsonl'),
                 deadline_uptime=deadline)
            save(controls/'config.json',cfg)
            execute([binary,controls/'config.json'],controls/'native.log',deadline,8)
            result=json.loads((controls/'native.log').read_text())
            edges=[json.loads(line) for line in (controls/'mapped_edges.jsonl').read_text().splitlines()]
            assert result['native_core_nodes']==2 and result['native_core_branches']==2
            assert result['positive_native_resistors']==1 and result['exact_zero_voltage_branches']==1
            positive=next(r for r in edges if r['branch_kind']=='positive_native_resistor')
            zero=next(r for r in edges if r['branch_kind']=='exact_zero_voltage_constraint')
            assert positive['nominal_conductance_siemens']==40 and positive['printed_native_resistance_ohm_token']=='0.025'
            assert positive['global_voltage_ids']==[1,2] and 'nominal_conductance_siemens' not in zero
            # A missing spatial voltage is a typed union requirement, never reference 0.
            (controls/'partial_R_nodes.jsonl').write_text('[1,"_rmesh_2_11"]\n')
            partial=dict(cfg,R_nodes=str(controls/'partial_R_nodes.jsonl'),
                node_output=str(controls/'partial_nodes.jsonl'),edge_output=str(controls/'partial_edges.jsonl'))
            save(controls/'partial.json',partial)
            execute([binary,controls/'partial.json'],controls/'partial.log',deadline,8)
            partial_result=json.loads((controls/'partial.log').read_text())
            assert partial_result['nodes_requiring_R_only_voltage_union']==1
            assert partial_result['branches_requiring_R_only_voltage_union']==2
            wrong=json.loads((controls/'nodes.json').read_text())
            wrong[0]['point_internal']=[99,7]
            save(controls/'wrong_nodes.json',wrong)
            bad=dict(cfg,nodes=str(controls/'wrong_nodes.json'),node_output=str(controls/'bad_nodes.jsonl'),
                edge_output=str(controls/'bad_edges.jsonl'))
            save(controls/'bad.json',bad)
            try:
                execute([binary,controls/'bad.json'],controls/'bad.log',deadline,8)
            except RuntimeError:
                pass
            else:
                raise ValueError('wrong native core coordinate identity accepted')
            config=out/'config.json'
            nout,eout=scratch/'native_core_nodes.jsonl',scratch/'native_core_branches.jsonl'
            save(config,dict(selected_groups=str(selected),nodes=str(nodes),R_nodes=str(rnodes),
                 provenance=str(provenance),node_output=str(nout),edge_output=str(eout),deadline_uptime=deadline))
            status('mapping_every_native_core_node_and_branch')
            execute([binary,config],out/'native.log',deadline,16)
            actual=json.loads((out/'native.log').read_text())
            native=json.loads(selected.read_text())
            if actual['native_core_nodes']!=native['native_node_count'] or actual['native_core_branches']!=native['native_branch_count']:
                raise ValueError('full native core node/branch coverage differs')
            with ThreadPoolExecutor(max_workers=8) as pool:
                if list(pool.map(sha,paths))!=list(pins.values()):
                    raise ValueError('native core source changed during mapping')
            products=[binary,config,nout,eout,out/'native.log',*[p for p in controls.iterdir() if p.is_file()]]
            save(out/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in products},
                 final_native_core_R_voltage_namespace_join_complete=True,results=actual,
                 native_core_float_bits_and_printed_R_tokens_retained=True,
                 positive_zero_missing_state_and_wrong_coordinate_controls_pass=True,
                 source_projection_assessment_pending=True,full_spatial_G_matrix_assembled=False,
                 material_and_resistance_PVT_qualified=False,physical_RC_qualified=False,
                 runtime_model_eligible=False,release_qualified=False))
            status('final_native_R_core_namespace_join_complete',results=actual)
            print(json.dumps(actual))
    except BaseException as error:
        status('failed',reason=repr(error))
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('extraction','snapshot','mapping','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    a=parser.parse_args()
    run(a.extraction,a.snapshot,a.mapping,a.output)
