#!/usr/bin/env python3
"""Connect current audited C/R and field-role data to native EXT geometry."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import time
from common import ROOT,save,sha
from compiled_charge import execute
from parallel_hash import sha_prefetch
from resources import lease


def run(a):
    mapping,audit,roles,out=[p.resolve() for p in (a.mapping,a.audit,a.roles,a.output)]
    out.mkdir(parents=True,exist_ok=False);deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    mr,ar,rr=[p/'assessment.json' for p in (mapping,audit,roles)]
    m,v,r=[json.loads(p.read_text()) for p in (mr,ar,rr)]
    if not v['all_field_associations_independently_checked'] or v['input_sha256'].get(str(mr))!=sha(mr):
        raise ValueError('matching complete typed C/R audit required')
    if not r['arithmetic_fields_emit_no_physical_operators'] or r['input_sha256'].get(str(mr))!=sha(mr):
        raise ValueError('matching verified arithmetic field roles required')
    dp=Path(m['common_native_layout_domain_receipt']);domain=json.loads(dp.read_text())
    if m['input_sha256'].get(str(dp))!=sha(dp):raise ValueError('native domain changed')
    gds=[(p,h) for p,h in domain['input_sha256'].items() if p.endswith('.gds')]
    if len(gds)!=1:raise ValueError('one exact source GDS required')
    ext=dp.parent/'trace/Prototype400_FilledCapacitanceView.ext'
    source=mapping/'native/field_domains.jsonl'
    catalog=json.loads((Path(m['source_catalog'])/'assessment.json').read_text())
    selection=Path(catalog['source_selection'])/'native_result.json'
    selected=json.loads(selection.read_text())
    if selected['status']!='pass' or not selected['final_res_ext_node_and_resistor_multisets_match']:
        raise ValueError('final native snapshot selection required')
    role_path=roles/'field_role_intervals.json';role=json.loads(role_path.read_text())
    native_source=ROOT/'tools/native_rc_coverage'
    sources=[native_source/'classify_ext_v3.cpp',native_source/'floating_geometry_v2.cpp']
    paths=[mr,ar,rr,dp,ext,source,selection,role_path,*sources,ROOT/'tools/charge_compiler/json.hpp',
           Path(__file__).resolve(),Path(__file__).with_name('parallel_hash.py'),Path(__file__).with_name('resources.py')]
    with lease(4,12,deadline):
        save(out/'status.json',dict(state='verifying_current_native_EXT_field_lineage',release_qualified=False))
        with ThreadPoolExecutor(max_workers=4) as pool:hashes=list(pool.map(lambda p:sha_prefetch(p,readers=2,deadline=deadline),paths))
        pins=dict(zip(map(str,paths),hashes))
        if (pins[str(ext)]!=domain['artifacts'][str(ext)] or pins[str(source)]!=m['artifacts'][str(source)] or pins[str(role_path)]!=r['artifacts'][str(role_path)] or pins[str(selection)]!=catalog['input_sha256'][str(selection)]):
            raise ValueError('native EXT/field/role artifact changed')
        groups=out/'selected_native_groups.jsonl';seen=set()
        with groups.open('x') as f:
            for entry in selected['selected_groups']:
                group=str(entry['group'])
                if group in seen:raise ValueError('duplicate final R snapshot')
                seen.add(group);f.write(json.dumps(dict(native_group_id=group,original_conductor=entry['original']))+'\n')
        expected=catalog['input_sha256'].get(str(selection.parent/'assessment.json'))
        if expected is None or sha(selection.parent/'assessment.json')!=expected:raise ValueError('selected catalog lineage changed')
        bins=[]
        for source_cpp in sources:
            binary=out/source_cpp.stem;bins.append(binary)
            execute(['g++','-std=c++20','-O3','-Wall','-Wextra','-Wpedantic',source_cpp,'-o',binary],out/(source_cpp.stem+'.build.log'),deadline,8)
        save(out/'status.json',dict(state='classifying_all_current_EXT_components',release_qualified=False))
        cfg=out/'ext.config.json';save(cfg,dict(ext=str(ext),groups=str(groups),inventory=str(source),output=str(out/'ext_inventory'),deadline_uptime=deadline))
        execute([bins[0],cfg],out/'ext.log',deadline,8)
        ex=json.loads((out/'ext_inventory/summary.json').read_text())
        if ex['fields']!=m['global_fields']:raise ValueError('full current field count differs')
        save(out/'status.json',dict(state='retaining_all_current_unextracted_native_geometries',release_qualified=False))
        cfg2=out/'geometry.config.json';interval=role['arithmetic_bookkeeping_field_id_interval']
        save(cfg2,dict(ext=str(ext),groups=str(groups),inventory=str(out/'ext_inventory/fields.jsonl'),output=str(out/'native'),deadline_uptime=deadline,
            arithmetic_field_begin=interval[0],arithmetic_field_end=interval[1]))
        execute([bins[1],cfg2],out/'geometry.log',deadline,8)
        result=json.loads((out/'native/summary.json').read_text())
        if result['unmatched_fields']!=ex['counts'].get('declared_component_without_port_device_or_native_R',0):
            raise ValueError('native EXT unmatched coverage differs')
        for p,h in pins.items():
            if sha_prefetch(Path(p),readers=4,deadline=deadline)!=h:raise ValueError('geometry source changed during inventory')
        artifacts=[*bins,groups,cfg,cfg2,out/'ext_inventory/summary.json',out/'ext_inventory/fields.jsonl',out/'native/summary.json',*sorted((out/'native').glob('nodes_*.jsonl'))]
        save(out/'assessment.json',dict(**result,input_sha256=pins,artifacts={str(p):sha_prefetch(p,deadline=deadline) for p in artifacts},
            shared_domain_sha256=pins[str(dp)],shared_geometry_sha256=gds[0][1],
            physical_and_arithmetic_field_ids_separated=True,EXT_inventory_counts=ex['counts'],EXT_records=ex['EXT_records'],
            no_isolation_or_ideal_conductor_assumption=True,physical_domain_complete=False,runtime_model_eligible=False))
        save(out/'status.json',dict(state='current_native_unextracted_geometry_inventory_complete',release_qualified=False))
        print(json.dumps(result))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('mapping','audit','roles','output'):p.add_argument('--'+name,required=True,type=Path)
    run(p.parse_args())
