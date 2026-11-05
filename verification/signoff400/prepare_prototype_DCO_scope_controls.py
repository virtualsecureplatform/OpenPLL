"""Prepare zero-wire-R scope controls while retaining each cell's local capacitance."""
import argparse,json
from pathlib import Path
from common_v3 import save,sha,verify
from prepare_prototype_analog_reference import subcircuits
from build_prototype_full_C_wire_R_v2 import Union,rows,expand
from audit_hierarchical_capacitance import number


def contract_wire_resistors(text,top):
    blocks=subcircuits(text);root=rows(blocks[top]);ports=root[0].split()[2:]
    aliases=Union();resistors=[]
    for line in root[1:-1]:
        f=line.split()
        if f[0][0].upper()=='R':
            if len(f)!=4 or number(f[3])<=0:raise ValueError('positive explicit wire resistance required')
            aliases.join(f[1],f[2]);resistors.append(f)
    if not resistors:raise ValueError('wire resistors required')
    primary={}
    for pin in ports:
        canonical=aliases.find(pin)
        if canonical in primary and primary[canonical]!=pin:raise ValueError('wire contraction shorts primary ports')
        primary[canonical]=pin
    def node(n):return primary.get(aliases.find(n),aliases.find(n))
    result=[root[0]];caps=0;cells=0
    for line in root[1:-1]:
        f=line.split();kind=f[0][0].upper()
        if kind=='R':continue
        if kind=='C':
            if len(f)!=4:raise ValueError('constant two-terminal capacitors required')
            f[1:3]=map(node,f[1:3]);caps+=1
        elif kind=='X':
            if f[-1] not in blocks:raise ValueError('isolated cell hierarchy required')
            interface=rows(blocks[f[-1]])[0].split()[2:]
            if len(f[1:-1])!=len(interface):raise ValueError('cell interface mismatch')
            f[1:-1]=map(node,f[1:-1]);cells+=1
        else:raise ValueError('unsupported top-level element')
        result.append(' '.join(f))
    result.append('.ends '+top)
    output='\n'.join(blocks[name] for name in blocks if name!=top)+'\n'+'\n'.join(result)+'\n'
    # Independent exact expansion of the zero-R reference proves all capacitor
    # signs and primitive topology survive the contraction, including aliases.
    reference=[]
    for line in root:
        f=line.split()
        reference.append(' '.join(f[:3]+['0']) if f[0][0].upper()=='R' else line)
    zero_blocks=dict(blocks);zero_blocks[top]='\n'.join(reference)+'\n'
    a=expand(zero_blocks,top);b=expand(subcircuits(output),top)
    # Union representatives differ, so project using the explicit quotient map.
    def rename(n):
        raw=n[len(top)+1:] if n.startswith(top+'/') else n
        projected=node(raw)
        return projected if projected in ports or projected=='0' else top+'/'+projected
    from collections import Counter,defaultdict
    from fractions import Fraction
    devices=Counter((m,tuple(rename(n) for n in ns),p) for m,ns,p in a[1])
    target=Counter((m,tuple(rename(n) for n in ns),p) for m,ns,p in b[1])
    def pairs(entries):
        result=defaultdict(Fraction)
        for (x,y),v in entries.items():
            x,y=rename(x),rename(y)
            if x!=y:result[tuple(sorted((x,y)))]+=v
        return {k:v for k,v in result.items() if v}
    if devices!=target or pairs(a[2])!=pairs(b[2]):raise ValueError('zero-R topology or capacitance operator differs')
    return output,dict(wire_resistors_contracted=len(resistors),top_level_capacitors_retained=caps,
        cell_instances_retained=cells,exact_zero_R_device_and_signed_C_identity_verified=True)


def run(rc,source,output):
    receipt=rc/'assessment.json';r=json.loads(receipt.read_text());verify(r['artifacts'])
    if not r['cell_internal_and_wire_capacitance_scopes_separated']:raise ValueError('conventional RC source required')
    cap_receipts=[Path(p) for p in r['input_sha256'] if p.endswith('/assessment.json') and 'capacitance' in p]
    if len(cap_receipts)!=1:raise ValueError('unique extraction lineage required')
    extraction=json.loads(cap_receipts[0].read_text())
    # Some extraction wrappers bind the capacitance file through their native receipt.
    if str(source) not in extraction.get('artifacts',{}):
        native=Path(extraction['source_extraction_directory'])/'native_assessment.json'
        extraction=json.loads(native.read_text())
    if extraction['artifacts'].get(str(source))!=sha(source):raise ValueError('full-C source lineage mismatch')
    conventional=rc/'nom.spice';top=source.parent.name
    model,metrics=contract_wire_resistors(conventional.read_text(),top)
    output.mkdir(parents=True,exist_ok=False)
    files=[output/'conventional_zero_wire_R.spice',output/'full_C_zero_wire_R.spice']
    files[0].write_text(model);files[1].write_text(source.read_text())
    paths=[receipt,*cap_receipts,source,conventional,Path(__file__).resolve(),Path(__file__).with_name('build_prototype_full_C_wire_R_v2.py')]
    pins={str(p):sha(p) for p in paths};verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(p):sha(p) for p in files},**metrics,
        cell_local_capacitance_not_globally_relocated=True,scope_control_only=True,
        native_scope_correlation_complete=False,parent_loading_complete=False,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('rc','source','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.rc.resolve(),a.source.resolve(),a.output.resolve())
