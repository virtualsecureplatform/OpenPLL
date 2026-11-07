"""Propagate the existing exact digital child short into the keeper parent LVS."""
import argparse,json,time,os
from pathlib import Path
from common_v3 import save,sha,verify
from replay_prototype_parent_port_alias_lvs import normalize,NETGEN
from resources import lease
from compiled_charge import execute


def run(source,drc,output):
    output.mkdir(parents=True,exist_ok=False);os.sched_setaffinity(0,{22,23})
    receipt=source/'assessment.json';r=json.loads(receipt.read_text());verify(r['input_sha256']);verify(r['artifacts'])
    drc_receipt=drc/'assessment.json';d=json.loads(drc_receipt.read_text());verify(d['input_sha256']);verify(d['artifacts'])
    gds=[p for p in r['input_sha256']if p.endswith('/assembly.gds')]
    if len(gds)!=1 or d['input_sha256'].get(gds[0])!=r['input_sha256'][gds[0]]or not d['Magic_full_flat_DRC_pass']:
        raise ValueError('same DRC-clean parent GDS required')
    raw=source/'assembly_alias_flattened.spice';text,proof=normalize(raw.read_text())
    model=output/'assembly_parent_alias_normalized.spice';model.write_text(text)
    old=source/'compare.tcl';recipe=old.read_text()
    if recipe.count(str(raw))!=1 or recipe.count(str(source/'compare.log'))!=1:raise ValueError('original LVS recipe differs')
    target=output/'compare.tcl';target.write_text(recipe.replace(str(raw),str(model)).replace(str(source/'compare.log'),str(output/'compare.log')))
    files=[Path(__file__).resolve(),Path(__file__).with_name('replay_prototype_parent_port_alias_lvs.py'),receipt,drc_receipt,raw,old,model,target,Path(NETGEN)]
    # Run inside the declared image and bind every actual schematic/setup input.
    for line in recipe.splitlines():
        f=line.split()
        if f and f[0]=='readnet'and len(f)>=3:files.append(Path(f[2]))
        if f and f[0]=='lvs':files.extend(Path(x)for x in f if x.startswith('/')and x.endswith('.tcl'))
    pins={str(p):sha(p)for p in files};save(output/'inputs.json',dict(input_sha256=pins,exact_alias_proof=proof))
    deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+600
    with lease(2,8,deadline):execute([NETGEN,'-batch','source',target],output/'native.log',deadline,8)
    native=(output/'native.log').read_text();log=(output/'compare.log').read_text();records=json.loads((output/'compare.json').read_text())
    if 'There were errors reading the setup file'in native or 'Error 'in native:raise ValueError('Netgen setup/runtime error')
    names=['IntegerPLL_ProgrammedCore','IntegerPLL_BBPD','IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8_LOAD36_C1FINE160']
    expanded=all(any(x.get('name')==[n,n]and all(sum(int(c)for _,c in side)>0 for side in x.get('devices',[]))for x in records)for n in names)
    clean=records[-1].get('name')==['IntegerPLL_400MHz_PrototypeTop']*2 and all(not x.get('badnets')and not x.get('badelements')and not x.get('properties')for x in records)
    unique='Final result: Circuits match uniquely.'in log and 'Property errors were found'not in log
    verify(pins);verify(r['input_sha256'])
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p)for p in [model,target,output/'native.log',output/'compare.log',output/'compare.json']},
        exact_parent_alias_proof=proof,all_three_macros_expanded=expanded,parent_LVS_match=unique and clean and expanded,
        all_records_without_discrepancies=clean,unfilled_parent_DRC_pass=True,fill_regeneration_required=True,
        antenna_density_power_and_analog_qualified=False,selected=False,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['source','drc','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve()for n in ['source','drc','output']))
