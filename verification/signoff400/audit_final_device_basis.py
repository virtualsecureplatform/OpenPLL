"""Independently join every final native device terminal and spatial voltage ID."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import time
from common import save,sha
from resources import lease


def run(mapping,snapshot,output):
    mapping,snapshot,out=(p.resolve() for p in (mapping,snapshot,output))
    out.mkdir(parents=True,exist_ok=False)
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+3600
    proof,final=snapshot/'assessment.json',mapping/'assessment.json'
    snap,report=[json.loads(p.read_text()) for p in (proof,final)]
    if not snap['final_res_ext_node_and_resistor_multisets_match'] or not report['final_native_device_basis_identity_inventory_complete']:
        raise ValueError('matching complete final snapshot and device identity map required')
    if report['input_sha256'].get(str(proof))!=sha(proof):
        raise ValueError('device map/final snapshot lineage differs')
    export=next(Path(p) for p in snap['input_sha256'] if p.endswith('.res.ext'))
    data=mapping/'device_basis_bindings.jsonl'
    cfg=json.loads((mapping/'config.json').read_text())
    rnodes=Path(cfg['R_nodes'])
    # These are source semantics, not assumptions about SPICE terminal ordering.
    print_source=next(Path(p) for p in snap['input_sha256'] if p.endswith('/resis/ResPrint.c') and '/tmp/' in p)
    header=print_source.with_name('resis.h')
    paths=[proof,final,export,data,rnodes,print_source,header,Path(__file__).resolve()]
    with lease(2,8,deadline):
        pins={str(p):sha(p) for p in paths}
        for p in (export,print_source,header):
            if pins[str(p)]!=snap['input_sha256'][str(p)]:
                raise ValueError('native final export/source changed')
        if pins[str(data)]!=report['artifacts'][str(data)] or pins[str(rnodes)]!=report['input_sha256'][str(rnodes)]:
            raise ValueError('device mapping/spatial identity source changed')
        text=header.read_text()
        for name,number in (('GATE',1),('SOURCE',2),('DRAIN',3),('SUBS',4)):
            if not re.search(r'^#define\s+'+name+r'\s+'+str(number)+r'\s*$',text,re.M):
                raise ValueError('native terminal enum semantics changed')
        code=print_source.read_text()
        for name in ('subs','gate','source','drain'):
            if f'devices->{name}->name' not in code:
                raise ValueError('native printed terminal source semantics changed')
        devices,private={},{}
        with data.open() as stream:
            for raw in stream:
                row=json.loads(raw)
                if row['basis_binding_state']!='exact_existing_spatial_voltage':
                    raise ValueError('this complete native terminal join requires all spatial bindings present')
                key=(row['model'],*row['point_internal'])
                device=devices.setdefault(key,dict(pointer=row['device_pointer'],type_id=row['type_id'],terminals={}))
                if device['pointer']!=row['device_pointer'] or device['type_id']!=row['type_id'] or row['terminal'] in device['terminals']:
                    raise ValueError('ambiguous native device identity or repeated terminal')
                device['terminals'][row['terminal']]=row
                prior=private.setdefault(row['private_id'],row['global_voltage_id'])
                if prior!=row['global_voltage_id']:
                    raise ValueError('private node maps to multiple spatial voltages')
        found=set()
        with rnodes.open() as stream:
            for raw in stream:
                number,name=json.loads(raw)
                if name in private:
                    if name in found or private[name]!=number:
                        raise ValueError('independent spatial node identity mismatch')
                    found.add(name)
        if found!=private.keys():
            raise ValueError('native terminal spatial voltage missing')
        counts,seen,terminal_count=Counter(),set(),0
        joined=out/'native_device_terminal_join.jsonl'
        order={4:0,1:1,2:2,3:3}
        with export.open() as stream,joined.open('w') as target:
            for line in stream:
                if not line.startswith('device '):
                    continue
                if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:
                    raise TimeoutError('independent device join deadline')
                head=line.split('"',1)[0].split()
                key=(head[2],int(head[3]),int(head[4]))
                if key not in devices or key in seen:
                    raise ValueError('native exported device missing or ambiguous in basis bindings')
                seen.add(key)
                device=devices[key]
                names=re.findall(r'"([^"]*)"',line)
                expected=({1,2} if 'diode_pw2nd' in key[0] else
                          {2,3} if 'res_generic_po' in key[0] else {1,2,3,4})
                if device['terminals'].keys()!=expected:
                    raise ValueError('native model terminal coverage mismatch')
                terminals=[]
                for terminal,row in sorted(device['terminals'].items()):
                    if len(names)<=order[terminal] or names[order[terminal]]!=row['printed_native_node']:
                        raise ValueError('native final exported terminal differs from spatial node binding')
                    terminal_count+=1
                    terminals.append([terminal,row['private_id'],row['global_voltage_id'],names[order[terminal]]])
                counts[key[0]]+=1
                target.write(json.dumps(dict(model=key[0],point_internal=list(key[1:]),
                     native_device_pointer=device['pointer'],terminals=terminals))+'\n')
        if seen!=devices.keys():
            raise ValueError('device basis identities absent from final native device export')
        if terminal_count!=report['results']['selected_binding_records']:
            raise ValueError('complete final device terminal record coverage mismatch')
        if any(sha(Path(p))!=h for p,h in pins.items()):
            raise ValueError('device join source changed during independent audit')
        save(out/'assessment.json',dict(input_sha256=pins,artifacts={str(joined):sha(joined)},
             all_final_native_device_terminals_independently_joined=True,
             all_terminal_global_voltage_ids_independently_checked=True,
             native_exported_devices=len(seen),native_exported_terminal_bindings=terminal_count,
             unique_spatial_device_voltage_nodes=len(private),native_model_device_counts=dict(counts),
             scope='native final res.ext device identities and terminal names; spatial private/global IDs',
             source_projection_assessment_pending=True,SPICE_device_parameter_join_verified=False,
             finite_R_substrate_target_assignment_qualified=False,
             physical_device_binding_qualified=False,runtime_model_eligible=False,
             physical_RC_qualified=False,release_qualified=False))
        print(json.dumps(dict(devices=len(seen),terminal_bindings=terminal_count,unique_spatial_nodes=len(private))))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('mapping','snapshot','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    a=parser.parse_args()
    run(a.mapping,a.snapshot,a.output)
