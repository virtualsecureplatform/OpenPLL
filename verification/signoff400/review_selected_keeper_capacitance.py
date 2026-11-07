"""Exactly certify the unchanged keeper capacitor network and ideal-supply subspace."""
import argparse,json,time
from pathlib import Path
from common_v3 import save,sha,verify
from prepare_prototype_analog_reference import subcircuits
from build_prototype_full_C_wire_R_v5 import expand
from check_prototype_capacitance_paths import certify
from project_prototype_fixed_rail_C_v2 import project,RAILS
from resources import lease


def run(source,output):
    receipt=source/'assessment.json';r=json.loads(receipt.read_text());verify(r['input_sha256']);verify(r['artifacts'])
    files=list(source.glob('*/capacitance.spice'))
    if len(files)!=1:raise ValueError('unique completed capacitor extraction required')
    raw=files[0];folder=Path(__file__).resolve().parent
    pins={str(p):sha(p)for p in [receipt,raw,Path(__file__).resolve(),*[folder/n for n in ['build_prototype_full_C_wire_R_v5.py','check_prototype_capacitance_paths.py','project_prototype_fixed_rail_C_v2.py']]]}
    output.mkdir(parents=True,exist_ok=False)
    with lease(1,8,time.clock_gettime(time.CLOCK_BOOTTIME)+600):
        ports,devices,pairs,aliases,_=expand(subcircuits(raw.read_text()),raw.parent.name)
        if not set(RAILS[1:])<=set(ports):raise ValueError('all four supply/body rails must be exposed')
        fixed={aliases.find(n)for n in RAILS}
        if {aliases.find('VPWR'),aliases.find('VPB')}&{aliases.find('VGND'),aliases.find('VNB')}:
            raise ValueError('positive and ground rails electrically shorted')
        projected=project(pairs,fixed)
        proofs={};artifacts={}
        for name,network in [('full',pairs),('ideal_supply',projected)]:
            path=output/(name+'.pairs.jsonl')
            with path.open('x')as f:
                for nodes,value in sorted(network.items()):f.write(json.dumps(dict(nodes=nodes,farads=str(value)))+'\n')
            proof=certify(network);proof_file=output/(name+'.proof.json');save(proof_file,proof)
            proofs[name]=proof;artifacts.update({str(p):sha(p)for p in [path,proof_file]})
    verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,top=raw.parent.name,
        expanded_devices=len(devices),full_capacitor_pairs=len(pairs),projected_capacitor_pairs=len(projected),
        full_network_passivity_certified=proofs['full']['passivity_certified'],
        ideal_supply_passivity_certified=proofs['ideal_supply']['passivity_certified'],
        fixed_voltage_nodes=sorted(fixed),ideal_constant_supply_assumption=True,
        full_capacitances_modified=False,wire_resistance_complete=False,parent_loading_complete=False,
        native_transient_qualified=False,selected=False,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.source.resolve(),a.output.resolve())
