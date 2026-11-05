"""Propagate an extracted exact-zero-ohm child port alias into parent instance nodes."""
import argparse,json,time,re,os
from pathlib import Path
from common_v3 import save,sha,verify
from prepare_prototype_analog_reference import subcircuits
from build_prototype_full_C_wire_R_v2 import rows,Union
from audit_hierarchical_capacitance import number
from resources import lease
from compiled_charge import execute

TOP='IntegerPLL_400MHz_PrototypeTop'
CHILD='IntegerPLL_ProgrammedCore'
NETGEN='/nix/store/kw3frc6fbv3zi2m9n0wv93y1nfiyjiy6-netgen-1.5.316/bin/netgen'


def normalize(text,top=TOP,child=CHILD):
    blocks=subcircuits(text);definition=rows(blocks[child]);interface=definition[0].split()[2:]
    wanted=('TRACKING','BBPD_RESET_N')
    if not set(wanted)<=set(interface):raise ValueError('required child alias ports absent')
    electrical=Union();witness=[]
    for line in definition[1:-1]:
        f=line.split()
        if f[0][0].upper()=='R' and len(f)==4 and number(f[3])==0:
            electrical.join(f[1],f[2]);witness.append(line)
    if electrical.find(wanted[0])!=electrical.find(wanted[1]):raise ValueError('child ports lack an explicit exact-zero-ohm connection')
    root=rows(blocks[top]);external=set(root[0].split()[2:]);aliases=Union();pairs=[]
    for line in root[1:-1]:
        f=line.split()
        if f[0][0].upper()!='X':raise ValueError('parent must contain only bound macro instances')
        if f[-1]==child:
            if len(f)!=len(interface)+2:raise ValueError('child instance port arity differs')
            a,b=[f[1+interface.index(pin)] for pin in wanted]
            if a in external and b in external and a!=b:raise ValueError('normalization cannot remove distinct external port identities')
            aliases.join(a,b);pairs.append(dict(instance=f[0],parent_nodes=[a,b],child_ports=list(wanted)))
    if len(pairs)!=1:raise ValueError('unique selected digital macro instance required')
    nodes={n for pair in pairs for n in pair['parent_nodes']};groups={}
    for n in nodes:groups.setdefault(aliases.find(n),set()).add(n)
    canonical={key:next(iter(value&external)) if value&external else min(value) for key,value in groups.items()}
    def mapped(n):return canonical.get(aliases.find(n),n)
    changed=[];rewritten=[root[0]]
    for line in root[1:-1]:
        f=line.split();before=f[1:-1];after=[mapped(n) for n in before]
        changed.extend(dict(instance=f[0],argument=i,old=a,new=b) for i,(a,b) in enumerate(zip(before,after)) if a!=b)
        rewritten.append(' '.join([f[0],*after,f[-1]]))
    rewritten.append(root[-1]);new='\n'.join(rewritten)+'\n'
    result=text.replace(blocks[top],new)
    if result==text or subcircuits(result)[child]!=blocks[child]:raise ValueError('expected parent-only alias substitution absent')
    return result,dict(exact_zero_R_witnesses=witness,alias_instances=pairs,changed_parent_arguments=changed,
        child_geometry_and_netlist_unchanged=True,top_external_port_list_unchanged=True,
        substitution_justified_only_by_exact_child_port_short=True)


def run(source,output):
    receipt=source/'assessment.json';r=json.loads(receipt.read_text());verify(r['input_sha256']);verify(r['artifacts'])
    raw=source/'assembly.spice';original=source/'compare.tcl';text,proof=normalize(raw.read_text())
    output.mkdir(parents=True,exist_ok=False);model=output/'assembly_alias_normalized.spice';model.write_text(text);detail=output/'alias_proof.json';save(detail,proof)
    recipe=output/'compare.tcl';tcl=original.read_text()
    if tcl.count(str(raw))!=1 or tcl.count(str(source/'compare.log'))!=1:raise ValueError('unique original LVS input/output required')
    recipe.write_text(tcl.replace(str(raw),str(model)).replace(str(source/'compare.log'),str(output/'compare.log')))
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+43200;os.environ.update(OMP_NUM_THREADS='4',OPENBLAS_NUM_THREADS='1',GOMAXPROCS='4')
    with lease(4,8,deadline):execute([NETGEN,'-batch','source',recipe],output/'native.log',deadline,8)
    log=(output/'compare.log').read_text();records=json.loads((output/'compare.json').read_text())
    unique='Final result: Circuits match uniquely.' in log and 'Property errors were found' not in log and 'Top level cell failed pin matching' not in log
    complete=records[-1]['name']==[TOP,TOP] and all(not row.get('badnets') and not row.get('badelements') for row in records)
    names=[CHILD,'IntegerPLL_BBPD','IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8_LOAD36_C1FINE160']
    expanded=all(any(row.get('name')==[name,name] and all(sum(int(count) for _,count in side)>0 for side in row['devices']) for row in records) for name in names)
    paths=[receipt,raw,original,model,detail,recipe,Path(NETGEN),Path(__file__).resolve()];pins={str(p):sha(p) for p in paths};verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in output.iterdir() if p.is_file()},
        assembled_drc_pass=r['assembled_drc_pass'],assembled_lvs_pass=unique and complete and expanded,
        all_three_macros_expanded=expanded,exact_zero_R_child_port_alias_propagated=True,
        original_extraction_preserved=True,native_extraction_simulations_started=0,
        parent_antenna_density_and_power_integrity_qualified=False,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('source','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.source.resolve(),a.output.resolve())
