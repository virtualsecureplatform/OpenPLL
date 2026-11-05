"""Eliminate unobserved constant voltage cuts used only by linear capacitors.

For C(v-u), prescribed constant u gives dQ/dt=C*dv/dt. Replace that
capacitor endpoint with ground and remove its ideal voltage source. Retained
nonlinear/resistive terminals and observations are protected. Absolute capacitor
charge/energy and individual removed-source currents require reconstruction.
This is exact at retained differential equations, not a physical-model or
numerical-convergence qualification.
"""
import argparse,json,math,re
from pathlib import Path
from common_v3 import save,sha,verify
from audit_selected_dco_history_inputs import sources


def logical(text):
    result=[]
    for line in text.splitlines():
        if line.startswith('+'):
            if not result:raise ValueError('orphan continuation')
            result[-1]+=' '+line[1:].strip()
        else:result.append(line)
    return result


def linear_cap(line):
    f=line.split()
    if len(f)!=4 or not f[0].lower().startswith('c'):return None
    try:value=float(f[3])
    except ValueError:return None
    return f if math.isfinite(value) else None


def identifiers(text):return {s.lower() for s in re.findall(r'[A-Za-z_][A-Za-z0-9_:\[\].]*',text)}


def transform(device_text,source_text,protected,deck_text=''):
    voltage={};source_lines=source_text.splitlines();protected={n.lower() for n in protected}
    for line in source_lines:
        f=line.split()
        if not f:continue
        if len(f)<4 or not f[0].lower().startswith('v') or f[2]!='0':raise ValueError('independent grounded voltage cuts required')
        if len(f)==4:
            try:value=float(f[3])
            except ValueError:continue
            if math.isfinite(value) and f[1].lower() not in protected:voltage[f[1].lower()]=(f[0].lower(),value)
    lines=logical(device_text);used=identifiers(deck_text);capacitor_nodes=set()
    for line in lines:
        if line.lstrip().startswith('*'):continue
        c=linear_cap(line)
        if c:capacitor_nodes.update(n.lower() for n in c[1:3])
        else:used.update(identifiers(line))
    # Protect nodes or source currents referenced by another source expression.
    for line in source_lines:
        f=line.split();used.update(identifiers(' '.join(f[3:])))
    eliminated={n:value for n,value in voltage.items() if n in capacitor_nodes and n not in used and value[0] not in used}
    rewritten=[];changed=removed=0
    for line in lines:
        c=linear_cap(line)
        if c and any(n.lower() in eliminated for n in c[1:3]):
            c[1:3]=['0' if n.lower() in eliminated else n for n in c[1:3]];changed+=1
            if c[1].lower()==c[2].lower():removed+=1;continue
            line=' '.join(c)
        rewritten.append(line)
    source_result=[line for line in source_lines if not line.split() or line.split()[1].lower() not in eliminated]
    return '\n'.join(rewritten)+'\n','\n'.join(source_result)+'\n',dict(eliminated_constant_nodes={n:dict(source=s,voltage=v) for n,(s,v) in sorted(eliminated.items())},changed_capacitors=changed,zero_current_capacitors_removed=removed)


def prepare(reference,output):
    output.mkdir(parents=True,exist_ok=False)
    manifest=reference/'manifest.json';m=json.loads(manifest.read_text());verify(m['input_sha256'])
    deck=(reference/'control.spice').read_text()
    if '*' in next(line for line in deck.splitlines() if line.lower().startswith('.print ')):raise ValueError('explicit retained observations required')
    devices,src,record=transform((reference/'devices.spice').read_text(),(reference/'sources.spice').read_text(),m['observed_roles'].values(),deck)
    if not record['eliminated_constant_nodes']:raise ValueError('no eligible constant capacitor cuts')
    (output/'devices.spice').write_text(devices);(output/'sources.spice').write_text(src)
    for name in ['devices.spice','sources.spice','control.raw']:
        if deck.count(str(reference/name))!=1:raise ValueError('one native reference per input/output required')
        deck=deck.replace(str(reference/name),str(output/name))
    (output/'control.spice').write_text(deck)
    pins={str(p):sha(p) for p in [manifest,reference/'devices.spice',reference/'sources.spice',reference/'control.spice',Path(__file__).resolve()]};verify(pins)
    save(output/'elimination.json',dict(input_sha256=pins,artifacts={str(output/name):sha(output/name) for name in ['devices.spice','sources.spice','control.spice']},**record,
        eliminated_node_count=len(record['eliminated_constant_nodes']),retained_differential_equations_identical=True,
        nonlinear_and_resistive_connections_unchanged=True,retained_observations_preserved=True,
        constant_cut_capacitor_charge_offsets_eliminated=True,removed_source_current_and_absolute_energy_preserved=False,
        numerical_convergence_qualified=False,physical_models_qualified=False,release_ready=False))
    return m

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    for name in ['reference','output']:parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();prepare(args.reference.resolve(),args.output.resolve())
