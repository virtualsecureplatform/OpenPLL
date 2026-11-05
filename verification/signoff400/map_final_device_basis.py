"""Retain final native device/private-node identities in the spatial namespace."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import shutil
import time
from common import ROOT,save,sha
from compiled_charge import execute
from resources import lease


def run(extraction,snapshot,mapping,output):
    extraction,snapshot,mapping,out=(p.resolve() for p in (extraction,snapshot,mapping,output))
    out.mkdir(parents=True,exist_ok=False)
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    index=(extraction/'domain_index').resolve()
    domain=(extraction/'domain').resolve()
    receipts=[index/'assessment.json',snapshot/'assessment.json',mapping/'assessment.json',domain/'assessment.json']
    idx,snap,maps,dom=[json.loads(p.read_text()) for p in receipts]
    if not snap['final_res_ext_node_and_resistor_multisets_match']:
        raise ValueError('complete final native R snapshot export proof required')
    for report in (idx,snap):
        if report['input_sha256'].get(str(receipts[3]))!=sha(receipts[3]):
            raise ValueError('final device index/snapshot domain lineage differs')
    selected=snapshot/'native_result.json'
    if sha(selected)!=snap['artifacts'][str(selected)]:
        raise ValueError('selected final native groups changed')
    mapcfg=json.loads((mapping/'config.json').read_text())
    rnodes=Path(mapcfg['R_nodes'])
    bindings,nodes=(index/name for name in ('device_bindings.json','nodes.json'))
    expected={str(p):idx['artifacts'][str(p)] for p in (bindings,nodes)}
    expected[str(rnodes)]=maps['input_sha256'][str(rnodes)]
    source=ROOT/'tools/sheet_charge/map_native_device_basis.cpp'
    compiler=Path(shutil.which('g++')).resolve()
    paths=[*receipts,selected,*map(Path,expected),source,source.parent.parent/'charge_compiler/json.hpp',
           compiler,Path(__file__).resolve()]
    def status(state,**extra):
        save(out/'status.json',dict(state=state,physical_device_binding_qualified=False,release_qualified=False,**extra))
    try:
        with lease(8,16,deadline):
            with ThreadPoolExecutor(max_workers=8) as pool:
                pins=dict(zip(map(str,paths),pool.map(sha,paths)))
            if any(pins[p]!=h for p,h in expected.items()):
                raise ValueError('device basis input changed')
            binary=out/'map_native_device_basis'
            execute([compiler,'-std=c++20','-O3','-Wall','-Wextra','-Wpedantic',
                     '-fno-fast-math','-ffp-contract=off',source,'-o',binary],out/'build.log',deadline,8)
            controls=out/'controls'
            controls.mkdir()
            save(controls/'selected.json',dict(selected_groups=[dict(group=2,original='netA')]))
            binding=[dict(device_pointer='0x1',point_internal=[999,999],type_id='18',model='nfet',
                     terminal=t,generation=g,private_id=f'_rmesh_2_{g}',original_conductor='netA',native_group_id='2')
                     for t,g in ((1,11),(2,12))]
            binding.append(dict(binding[0],native_group_id='1',private_id='_rmesh_1_11'))
            save(controls/'bindings.json',binding)
            fixture_nodes=[dict(private_id=f'_rmesh_2_{g}',native_pointer=f'0x{g}',
                original_conductor='netA',printed_name=f'netA.n{g}',point_internal=[g,7],native_group_id='2')
                for g in (11,12)]
            save(controls/'nodes.json',fixture_nodes)
            (controls/'R_nodes.jsonl').write_text('[1,"_rmesh_2_11"]\n')
            cfg=dict(selected_groups=str(controls/'selected.json'),bindings=str(controls/'bindings.json'),
                     nodes=str(controls/'nodes.json'),R_nodes=str(controls/'R_nodes.jsonl'),
                     output=str(controls/'mapped.jsonl'),deadline_uptime=deadline)
            save(controls/'config.json',cfg)
            execute([binary,controls/'config.json'],controls/'native.log',deadline,8)
            summary=json.loads((controls/'native.log').read_text())
            rows=[json.loads(s) for s in (controls/'mapped.jsonl').read_text().splitlines()]
            assert summary['selected_binding_records']==2 and summary['superseded_binding_records_retained_in_source']==1
            assert rows[0]['global_voltage_id']==1 and rows[0]['native_node_point_internal']==[11,7]
            assert rows[0]['point_internal']==[999,999] and not rows[0]['device_location_is_terminal_geometry']
            assert rows[1]['basis_binding_state']=='requires_R_only_voltage_union' and 'global_voltage_id' not in rows[1]
            for label,bad in (('missing_private',[fixture_nodes[0]]),
                              ('wrong_conductor',[dict(fixture_nodes[0],original_conductor='wrong'),fixture_nodes[1]])):
                save(controls/(label+'.json'),bad)
                badcfg=dict(cfg,nodes=str(controls/(label+'.json')),output=str(controls/(label+'.jsonl')))
                save(controls/(label+'.config.json'),badcfg)
                try:
                    execute([binary,controls/(label+'.config.json')],controls/(label+'.log'),deadline,8)
                except RuntimeError:
                    pass
                else:
                    raise ValueError('invalid device/private binding accepted: '+label)
            status('mapping_all_final_native_device_bindings')
            cfg=out/'config.json'
            result=out/'device_basis_bindings.jsonl'
            save(cfg,dict(selected_groups=str(selected),bindings=str(bindings),nodes=str(nodes),
                 R_nodes=str(rnodes),output=str(result),deadline_uptime=deadline))
            execute([binary,cfg],out/'native.log',deadline,16)
            actual=json.loads((out/'native.log').read_text())
            if actual['selected_native_groups']!=snap['selected_group_count']:
                raise ValueError('final device group coverage differs')
            with ThreadPoolExecutor(max_workers=8) as pool:
                if list(pool.map(sha,paths))!=list(pins.values()):
                    raise ValueError('device mapping input changed during processing')
            products=[binary,cfg,result,out/'native.log',*controls.glob('*')]
            save(out/'assessment.json',dict(input_sha256=pins,
                 artifacts={str(p):sha(p) for p in products if p.is_file()},
                 final_native_device_basis_identity_inventory_complete=True,
                 private_identity_controls_and_two_negative_cases_pass=True,results=actual,
                 source_projection_assessment_pending=True,
                 unrepresented_native_device_nodes_never_ideal_conductor_fallback=True,
                 logical_device_instance_terminal_join_complete=False,
                 physical_device_binding_qualified=False,full_R_only_voltage_union_assembled=False,
                 runtime_model_eligible=False,physical_RC_qualified=False,release_qualified=False))
            status('final_device_basis_identity_inventory_complete',results=actual)
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
