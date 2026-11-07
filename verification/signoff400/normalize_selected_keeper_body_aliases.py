"""Flatten four HS instances using only their extracted exact-zero-ohm aliases."""
import argparse,json,time
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from prepare_prototype_analog_reference import subcircuits
from build_prototype_full_C_wire_R_v2 import rows,Union
from resources import lease
from compiled_charge import execute

CHILD='sky130_fd_sc_hs__inv_2'


def normalize(text,top):
    blocks=subcircuits(text);child=rows(blocks[CHILD]);ports=child[0].split()[2:]
    if set(ports)!=set(['A','Y','VPWR','VGND','VPB','VNB']):raise ValueError('HS six-pin definition required')
    shorts=[];devices=[];cu=Union()
    for line in child[1:-1]:
        f=line.split()
        if f[0].upper().startswith('R'):
            if len(f)!=4 or float(f[3])!=0:raise ValueError('only explicit zero resistors may be substituted')
            shorts.append(line);cu.join(f[1],f[2])
        elif f[0].upper().startswith('X') and f[5].startswith('sky130_fd_pr__'):devices.append(f)
        else:raise ValueError('unexpected HS primitive')
    if len(shorts)!=2 or len(devices)!=4 or cu.find('VPB')!=cu.find('VPWR') or cu.find('VNB')!=cu.find('VGND'):
        raise ValueError('expected two supply/body short witnesses and four MOS')
    root=rows(blocks[top]);external=set(root[0].split()[2:]);pu=Union();instances=[]
    for line in root[1:-1]:
        f=line.split()
        if f[0][0].upper()!='X':raise ValueError('expected cell-only top')
        if f[-1]==CHILD:
            if len(f)!=len(ports)+2:raise ValueError('HS instance arity mismatch')
            binding=dict(zip(ports,f[1:-1]));instances.append((f,binding))
            for line in shorts:
                _,a,b,_=line.split();pu.join(binding[a],binding[b])
    if len(instances)!=4:raise ValueError('exactly four HS instances required')
    groups={}
    for _,binding in instances:
        for n in binding.values():groups.setdefault(pu.find(n),set()).add(n)
    canonical={}
    for key,group in groups.items():
        ext=group&external
        if len(ext)>1:raise ValueError('cannot merge distinct external ports')
        canonical[key]=next(iter(ext))if ext else min(group)
    def mapped(n):return canonical.get(pu.find(n),n)
    rewritten=[root[0]];changes=[]
    for line in root[1:-1]:
        f=line.split()
        if f[-1]!=CHILD:
            nodes=[mapped(n)for n in f[1:-1]]
            changes.extend(dict(instance=f[0],old=a,new=b)for a,b in zip(f[1:-1],nodes)if a!=b)
            rewritten.append(' '.join([f[0],*nodes,f[-1]]));continue
        binding=dict(zip(ports,f[1:-1]))
        for d in devices:
            # Each primitive and its parameters are copied; only its node arguments are bound.
            nodes=[mapped(binding[n])for n in d[1:5]]
            rewritten.append(' '.join([f[0]+'__'+d[0],*nodes,*d[5:]]))
    rewritten.append(root[-1])
    result=text.replace(blocks[top],'\n'.join(rewritten)+'\n').replace(blocks[CHILD],'')
    return result,dict(exact_zero_resistor_witnesses=shorts,HS_instances=[f[0]for f,_ in instances],
        expanded_MOS_count=16,changed_other_instance_arguments=changes,top_port_order_unchanged=True,
        original_four_MOS_per_cell_and_parameters_preserved=True,geometry_unchanged=True)


def run(replay,output):
    output.mkdir(parents=True,exist_ok=False);inputs=replay/'inputs.json';i=json.loads(inputs.read_text());verify(i['input_sha256'])
    flow=replay/'runs/gds_lvs';raw=next(flow.glob('*magic-spiceextraction/*.spice'));recipe=next(flow.glob('*netgen-lvs/lvs_script.lvs'))
    top=raw.stem;text,proof=normalize(raw.read_text(),top);model=output/'alias_flattened.spice';model.write_text(text)
    old_report=next(flow.glob('*netgen-lvs/reports/lvs.netgen.rpt'));report=output/'lvs.rpt'
    tcl=recipe.read_text()
    if tcl.count(str(raw))!=1 or tcl.count(str(old_report))!=1:raise ValueError('unique native LVS input/output required')
    target=output/'compare.tcl';target.write_text(tcl.replace(str(raw),str(model)).replace(str(old_report),str(report)))
    image=ROOT/'build/apptainer/openpll-release-modern.sif'
    pins={str(p):sha(p)for p in [Path(__file__).resolve(),inputs,raw,recipe,model,target,image]}
    save(output/'inputs.json',dict(input_sha256=pins,proof=proof))
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+600
    command=['apptainer','exec','--bind','/home:/home,/tmp:/tmp','--env','PATH=/nix/store/nah36l3f04m5gsi98a7civz9n8szraml-devshell-dir/bin:/usr/bin:/bin',str(image),'netgen','-batch','source',str(target)]
    with lease(2,8,deadline):execute(command,output/'native.log',deadline,8)
    records=json.loads(report.with_suffix('.json').read_text());log=report.read_text()
    unique='Final result: Circuits match uniquely.'in log and 'Property errors were found'not in log
    complete=records[-1].get('name')==[top,top]and all(not r.get('badnets')and not r.get('badelements')and not r.get('properties')for r in records)
    verify(pins);verify(i['input_sha256'])
    save(output/'assessment.json',dict(input_sha256=pins,replay_input_sha256=i['input_sha256'],proof=proof,
        artifacts={str(p):sha(p)for p in [model,target,report,report.with_suffix('.json'),output/'native.log']},
        normalized_GDS_LVS_pass=unique and complete,all_records_without_discrepancies=complete,
        original_LVS_preserved=True,selected=False,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--replay',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.replay.resolve(),a.output.resolve())
