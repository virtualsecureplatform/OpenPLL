"""Join native SPICE device parameters to independently audited spatial terminals."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import re
import time
from common import save,sha
from resources import lease


def xcards(path):
    cards={}
    pending=None
    def finish():
        if pending is not None:
            tokens=pending.decode('ascii').split()
            if tokens[0] in cards:
                raise ValueError('duplicate native SPICE instance')
            cards[tokens[0]]=tokens
    with path.open('rb') as stream:
        for line in stream:
            if line.startswith(b'+') and pending is not None:
                pending+=b' '+line[1:].strip()
                continue
            finish()
            pending=line.strip() if line.startswith(b'X') else None
        finish()
    return cards


def join_device(before,after,geometry):
    model=geometry['model']
    if before[0]!=after[0]:
        raise ValueError('SPICE instance identity changed')
    if before.count(model)!=1 or after.count(model)!=1:
        raise ValueError('unique native model token required')
    a,b=before.index(model),after.index(model)
    if a!=b or before[a:]!=after[b:]:
        raise ValueError('native model or parameter tokens changed')
    terminals={row[0]:row for row in geometry['terminals']}
    if set(terminals)=={1,2,3,4}:
        order=[3,1,2,4]
    elif set(terminals)=={1,2}:
        order=[2,1]  # Native two-terminal MOS-like diode subcircuit.
    elif set(terminals)=={2,3}:
        order=[2,3]  # Native resistor subcircuit omits its identifier gate.
    else:
        raise ValueError('unsupported native device terminal set')
    if len(order)!=a-1 or after[1:b]!=[terminals[t][3] for t in order]:
        raise ValueError('native SPICE terminal order differs from audited native export')
    return [after[0],*[terminals[t][1] for t in order],*after[b:]],order


def controls():
    count=0
    for model,order in (('nfet',[3,1,2,4]),('diode',[2,1]),('resistor',[2,3])):
        geometry=dict(model=model,terminals=[[t,f'_rmesh_2_{t}',100+t,f'net.t{t}'] for t in sorted(order)])
        before=['X7',*[f'old{t}' for t in order],model,'w=1','l=0.15']
        after=['X7',*[f'net.t{t}' for t in order],model,'w=1','l=0.15']
        actual,sequence=join_device(before,after,geometry)
        assert sequence==order and actual[1:1+len(order)]==[f'_rmesh_2_{t}' for t in order]
        for changed in (after[:-1]+['l=9'],[after[0],'wrong',*after[2:]]):
            try:
                join_device(before,changed,geometry)
            except ValueError:
                count+=1
            else:
                raise ValueError('invalid native parameter/terminal control accepted')
    return count


def run(extraction,snapshot,audit,output):
    extraction,snapshot,audit,out=(p.resolve() for p in (extraction,snapshot,audit,output))
    out.mkdir(parents=True,exist_ok=False)
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    domain=(extraction/'domain').resolve()
    receipts=[domain/'assessment.json',snapshot/'assessment.json',audit/'assessment.json']
    dom,snap,checked=[json.loads(p.read_text()) for p in receipts]
    if not checked['all_final_native_device_terminals_independently_joined'] or not checked['all_terminal_global_voltage_ids_independently_checked']:
        raise ValueError('complete independent spatial terminal audit required')
    if checked['input_sha256'].get(str(receipts[1]))!=sha(receipts[1]) or snap['input_sha256'].get(str(receipts[0]))!=sha(receipts[0]):
        raise ValueError('native device/domain/snapshot lineage differs')
    before,after,trace=(domain/'trace'/n for n in ('pre_resistance.spice','retained_rc.spice','SPICE_devices.log'))
    geometry=audit/'native_device_terminal_join.jsonl'
    code=next(Path(p) for p in snap['input_sha256'] if p.endswith('/ext2spice/ext2spice.c'))
    paths=[*receipts,before,after,trace,geometry,code,Path(__file__).resolve()]
    def status(state,**extra):
        save(out/'status.json',dict(state=state,runtime_model_eligible=False,release_qualified=False,**extra))
    try:
        with lease(8,8,deadline):
            with ThreadPoolExecutor(max_workers=8) as pool:
                pins=dict(zip(map(str,paths),pool.map(sha,paths)))
            for p in (before,after,trace):
                if pins[str(p)]!=dom['artifacts'][str(p)]:
                    raise ValueError('native SPICE or geometry trace changed')
            if pins[str(geometry)]!=checked['artifacts'][str(geometry)] or pins[str(code)]!=snap['input_sha256'][str(code)]:
                raise ValueError('audited geometry or native device writer changed')
            source=code.read_text()
            for token in ('OPENPLL_SPICE_DEVICE_TRACE_FILE','dev->dev_rect.r_xbot','esSbckNum - 1'):
                if token not in source:
                    raise ValueError('native instance/geometry tracing semantics changed')
            negative=controls()
            phases=[{}]
            with trace.open() as stream:
                for line in stream:
                    match=re.fullmatch(r'DEVICE (\S+) "([^"]+)" (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+)\n',line)
                    if not match:
                        raise ValueError('unsupported native SPICE geometry trace')
                    name,model,*numbers=match.groups()
                    if name in phases[-1]:
                        if name!='X0' or len(phases)!=1:
                            raise ValueError('ambiguous SPICE trace export phase')
                        phases.append({})
                    phases[-1][name]=(model,*map(int,numbers))
            if len(phases)!=2 or phases[0]!=phases[1]:
                raise ValueError('pre/post resistance SPICE device geometry identity differs')
            physical={}
            with geometry.open() as stream:
                for line in stream:
                    row=json.loads(line)
                    key=(row['model'],*row['point_internal'])
                    if key in physical:
                        raise ValueError('ambiguous physical device geometry')
                    physical[key]=row
            status('reading_complete_native_SPICE_device_cards')
            with ThreadPoolExecutor(max_workers=2) as pool:
                pre,post=list(pool.map(xcards,(before,after)))
            if pre.keys()!=post.keys() or post.keys()!=phases[1].keys() or len(post)!=len(physical):
                raise ValueError('complete native geometry/SPICE instance coverage differs')
            seen=set()
            fragment,ledger=out/'devices.spice',out/'device_parameter_join.jsonl'
            with fragment.open('w') as target,ledger.open('w') as details:
                target.write('* Native model/parameter tokens with audited spatial private terminals\n')
                for name in sorted(post,key=lambda n:int(n[1:])):
                    if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:
                        raise TimeoutError('spatial device parameter join deadline')
                    key=phases[1][name][:3]
                    if key not in physical or key in seen:
                        raise ValueError('native instance has missing or reused physical geometry')
                    seen.add(key)
                    row,order=join_device(pre[name],post[name],physical[key])
                    target.write(' '.join(row)+'\n')
                    details.write(json.dumps(dict(instance=name,model=key[0],point_internal=list(key[1:]),
                         native_trace_geometry=list(phases[1][name][1:]),native_terminal_order=order,
                         global_voltage_ids=[{r[0]:r[2] for r in physical[key]['terminals']}[t] for t in order],
                         original_native_card=pre[name],retained_native_card=post[name],spatial_card=row))+'\n')
            if seen!=physical.keys():
                raise ValueError('unjoined physical device geometry')
            with ThreadPoolExecutor(max_workers=8) as pool:
                if list(pool.map(sha,paths))!=list(pins.values()):
                    raise ValueError('spatial device join input changed during processing')
            save(out/'assessment.json',dict(input_sha256=pins,
                 artifacts={str(p):sha(p) for p in (fragment,ledger)},
                 native_SPICE_device_parameter_and_terminal_join_verified=True,
                 native_device_count=len(post),native_geometry_export_phases=2,
                 positive_terminal_order_controls=3,negative_parameter_terminal_controls=negative,
                 native_model_and_parameter_tokens_preserved_exactly=True,
                 diode_parameter_scaling_changed=False,model_physical_compatibility_qualified=False,
                 source_projection_assessment_pending=True,
                 finite_R_substrate_target_assignment_qualified=False,physical_device_binding_qualified=False,
                 runtime_model_eligible=False,physical_RC_qualified=False,release_qualified=False))
            status('native_SPICE_device_parameters_joined_to_spatial_terminals',devices=len(post))
            print(json.dumps(dict(native_devices=len(post),native_SPICE_device_parameter_and_terminal_join_verified=True)))
    except BaseException as error:
        status('failed',reason=repr(error))
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('extraction','snapshot','audit','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    a=parser.parse_args()
    run(a.extraction,a.snapshot,a.audit,a.output)
