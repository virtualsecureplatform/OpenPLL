"""Check actual EXT port locations and resistor S/D anchors for MOS-diffusion exceptions."""
import argparse,json,shlex
from collections import defaultdict
from fractions import Fraction as F
from pathlib import Path
from common_v3 import save,sha,verify
from audit_keeper_flat_MOS_region_join import Aliases

def run(coverage,output):
    receipt=coverage/'assessment.json';a=json.loads(receipt.read_text());verify(a['input_sha256']);verify(a['artifacts'])
    ext=next(Path(p) for p in a['input_sha256'] if p.endswith('/IntegerPLL_400MHz_KeeperFlatC.ext'));detail=coverage/'without_MOS_diffusion.json';rows=json.loads(detail.read_text());aliases=Aliases()
    files=[receipt,ext,detail,Path(__file__).resolve(),Path(__file__).with_name('audit_keeper_flat_MOS_region_join.py')];pins={str(p):sha(p) for p in files}
    for line in ext.open():
        if line.startswith('equiv '):
            f=shlex.split(line);aliases.union(f[1],f[2])
    ports=defaultdict(list);resistors=defaultdict(list)
    for line in ext.open():
        if line.startswith('port '):
            f=shlex.split(line)
            if len(f)!=8:raise ValueError('explicit EXT port coordinates required')
            box=list(map(int,f[3:7]));ports[aliases.find(f[1])].append(dict(name=f[1],index=int(f[2]),bbox_EXT_units=box,layer=f[7]))
        elif line.startswith('device rsubckt '):
            f=shlex.split(line);i=7;params={}
            while '=' in f[i]:
                n,v=f[i].split('=',1);params[n]=v;i+=1
            if f[2]!='sky130_fd_pr__res_generic_po' or len(f[i:])!=10 or F(params['w'])<=0:raise ValueError('checked positive-width poly resistor encoding required')
            for role,index in [('source',i+4),('drain',i+7)]:
                resistors[aliases.find(f[index])].append(dict(model=f[2],legacy_terminal_role=role,device_location_EXT_units=list(map(int,f[3:5])),width_EXT_units=params['w']))
    records=[]
    for row in rows:
        node=row['canonical_node'];p=ports[node];r=resistors[node]
        records.append(dict(**row,native_port_locations=p,native_poly_source_or_drain_anchors=r,structural_driver_anchor_present=bool(p or r)))
    verify(pins);output.mkdir(parents=True,exist_ok=False);save(output/'anchors.json',records)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(output/'anchors.json'):sha(output/'anchors.json')},exception_nodes=len(records),exception_nodes_with_native_port_location=sum(bool(r['native_port_locations']) for r in records),exception_nodes_with_poly_source_or_drain_anchor=sum(bool(r['native_poly_source_or_drain_anchors']) for r in records),exception_nodes_without_structural_anchor=sum(not r['structural_driver_anchor_present'] for r in records),all_exceptions_have_structural_anchor=all(r['structural_driver_anchor_present'] for r in records),all_native_port_records=sum(map(len,ports.values())),native_port_conductors_with_multiple_port_records=sum(len(p)>1 for p in ports.values()),native_resistance_extraction_executed=False,exact_native_skip_set_verified=False,distributed_wire_R_qualified=False,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['coverage','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.coverage.resolve(),a.output.resolve())
