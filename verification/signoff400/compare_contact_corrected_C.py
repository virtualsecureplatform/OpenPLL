"""Compare completed flat native exports without accepting capacitance identity."""
import argparse,json
from collections import Counter,defaultdict
from fractions import Fraction
from pathlib import Path
from runtime_common import save,sha
from native_spice_comments import strip_floating_annotation
from audit_hierarchical_capacitance import number


def inventory(text):
    cards=[]
    for raw in text.splitlines():
        line=strip_floating_annotation(raw).strip()
        if not line or line.startswith('*'):continue
        if line.startswith('+'):
            if not cards:raise ValueError('orphan continuation')
            cards[-1]+=' '+line[1:]
        else:cards.append(line)
    devices=Counter();caps=defaultdict(Fraction);ports=None;ended=False
    for line in cards:
        f=line.split();kind=f[0][0].upper()
        if f[0].lower()=='.subckt':
            if ports is not None:raise ValueError('one flat subcircuit required')
            ports=f[1:]
        elif f[0].lower()=='.ends':ended=True
        elif kind=='C':
            if len(f)!=4:raise ValueError('four-field capacitor required')
            value=number(f[3])
            if value<0:raise ValueError('negative native branch requires separate review')
            caps[tuple(sorted(f[1:3]))]+=value
        elif kind in 'XRM':devices[tuple(f[1:])+(kind,)]+=1
        else:raise ValueError('unsupported native card: '+f[0])
    if ports is None or not ended:raise ValueError('complete flat subcircuit required')
    return ports,devices,dict(caps)


def compare(old,new):
    op,od,oc=inventory(old);np,nd,nc=inventory(new)
    if op!=np or od!=nd:raise ValueError('native ports or device/connectivity cards changed')
    changed=[]
    for pair in sorted(set(oc)|set(nc)):
        a,b=oc.get(pair,Fraction()),nc.get(pair,Fraction())
        if a!=b:changed.append(dict(nodes=list(pair),old_F=str(a),new_F=str(b),delta_F=str(b-a)))
    return dict(device_cards=sum(od.values()),ports_and_device_cards_identical=True,
                changed_pairs=changed,old_pairs=len(oc),new_pairs=len(nc))


def run(old,new,output):
    records=[];pins={}
    for directory in [old,new]:
        if json.loads((directory/'status.json').read_text())['state']!='flat_geometry_C_extracted_independent_checks_pending':
            raise ValueError('completed native extraction required before waveform/model reading')
        receipt=directory/'assessment.json';record=json.loads(receipt.read_text());records.append(record)
        pins[str(receipt)]=sha(receipt)
        for path in [directory/'capacitance.spice']:
            if record['artifacts'].get(str(path))!=sha(path):raise ValueError('native export digest mismatch')
            pins[str(path)]=sha(path)
    if records[0]['source_GDS_sha256']!=records[1]['source_GDS_sha256']:
        raise ValueError('same checked source GDS required')
    result=compare((old/'capacitance.spice').read_text(),(new/'capacitance.spice').read_text())
    output.mkdir(exist_ok=False);changes=output/'changed_pairs.json';save(changes,result.pop('changed_pairs'))
    save(output/'assessment.json',dict(input_sha256={**pins,str(Path(__file__).resolve()):sha(Path(__file__).resolve())},
         artifacts={str(changes):sha(changes)},changed_pairs=len(json.loads(changes.read_text())),**result,
         coefficient_changes_measured=True,full_geometry_qualified=False,wire_R_qualified=False,
         native_simulation_allowed=False,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ['old','new','output']:p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();run(a.old.resolve(),a.new.resolve(),a.output.resolve())
