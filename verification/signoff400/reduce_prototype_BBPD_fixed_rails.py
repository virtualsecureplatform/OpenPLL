"""Exact card/capacitor-preserving signal reduction under explicitly ideal constant rails."""
import argparse
from collections import Counter,defaultdict
from fractions import Fraction as F
import json
from pathlib import Path
from common_v3 import ROOT,save,sha,verify
from prepare_prototype_analog_reference import subcircuits
from compare_prototype_analog_devices_v2 import devices
from prototype_capacitance_aliases import flatten
from build_prototype_DCO_rc import decimal

RAILS={'VPWR','VPB','VGND','VNB','0'}


def normalize(n):return '/'.join(p[1:] if p.startswith('Xsky130_fd_sc_hd__') else p for p in n.split('/'))


def exact(v):
    text=decimal(F(v))
    if F(text)!=F(v):raise ValueError('decimal conversion lost exact value')
    return text


def reduce(text):
    top='IntegerPLL_BBPD';blocks=subcircuits(text);cards=devices(blocks,top);caps,counts,canonical=flatten(blocks,top)
    ports=[]
    for line in blocks[top].splitlines():
        if not ports:ports=line.split()[2:]
        elif line.startswith('+'):ports+=line.split()[1:]
        else:break
    if not RAILS-{'0'}<=set(ports):raise ValueError('explicit four-rail interface required')
    classes={p:normalize(canonical(p)) for p in ports};fixed={classes[p] for p in RAILS-{'0'}}|{'0'}
    retained=Counter();removed=Counter()
    for card,count in cards.items():
        (removed if set(card[1])<=fixed else retained)[card]+=count
    normalized_caps=defaultdict(F);cap_labels={}
    for nodes,value in caps.items():
        normalized=[]
        for n in nodes:
            key=normalize(n)
            if key in cap_labels and cap_labels[key]!=n:raise ValueError('ambiguous capacitor hierarchy normalization')
            cap_labels[key]=n;normalized.append(key)
        if normalized[0]!=normalized[1]:normalized_caps[tuple(sorted(normalized))]+=value
    retained_caps={k:v for k,v in normalized_caps.items() if v and not set(k)<=fixed}
    names={};aliases=[]
    for p in ports:
        key=classes[p]
        if key in names:aliases.append((p,names[key]))
        else:names[key]=p
    names['0']='0'
    all_nodes={n for card in retained for n in card[1]}|{n for pair in retained_caps for n in pair}
    for n in sorted(all_nodes):
        if n not in names:names[n]='__fixed_signal_'+str(len(names))
    lines=['* Signal-only reduction: ideal constant rails; power/current/nonideal supply excluded.', '.subckt '+top+' '+' '.join(ports)]
    lines.extend(f'Ralias{i} {a} {b} 0' for i,(a,b) in enumerate(aliases))
    index=0
    for (model,nodes,params),count in sorted(retained.items()):
        for _ in range(count):
            lines.append('X'+str(index)+' '+' '.join(names[n] for n in nodes)+' '+model+' '+' '.join(k+'='+exact(v) for k,v in params));index+=1
    for i,(pair,value) in enumerate(sorted(retained_caps.items())):lines.append(f'C{i} {names[pair[0]]} {names[pair[1]]} {exact(value)}')
    lines.append('.ends '+top);result='\n'.join(lines)+'\n'
    # Independent reparse checks all retained cards and signed capacitor values.
    reparsed=subcircuits(result);inverse={v:k for k,v in names.items()}
    def original_node(n):
        key=n[len(top)+1:] if n.startswith(top+'/') else n
        if key not in inverse:raise ValueError('unknown reparsed reduced node')
        return inverse[key]
    replay=Counter()
    for (model,nodes,params),count in devices(reparsed,top).items():replay[(model,tuple(original_node(n) for n in nodes),params)]+=count
    if replay!=retained:raise ValueError('retained primitive cards changed in reduction')
    replay_caps,_,_=flatten(reparsed,top)
    translated=defaultdict(F)
    for pair,value in replay_caps.items():translated[tuple(sorted(original_node(n) for n in pair))]+=value
    if dict(translated)!=retained_caps:raise ValueError('retained signed capacitance changed in reduction')
    return result,dict(original_primitives=sum(cards.values()),removed_fixed_terminal_primitives=sum(removed.values()),retained_primitives=sum(retained.values()),
        original_aggregated_capacitor_pairs=len(normalized_caps),retained_signed_capacitor_pairs=len(retained_caps),
        removed_fixed_rail_capacitor_pairs=len(normalized_caps)-len(retained_caps),port_aliases=aliases,
        retained_cards_and_signed_caps_independently_reparsed_exactly=True,
        scope='Deterministic signal voltages, four ideal constant rails, fixed global temperature; no shared thermal state.',
        power_supply_current_noise_and_nonideal_rails_preserved=False,full_vs_reduced_native_waveform_correlation_complete=False)


def run(output):
    output.mkdir(parents=True,exist_ok=False);source=ROOT/'build/signoff400/prototype_v3_analog_capacitance_002'
    receipt=source/'native_assessment.json';model=source/'IntegerPLL_BBPD/capacitance.spice';r=json.loads(receipt.read_text())
    if r['artifacts'].get(str(model))!=sha(model):raise ValueError('native BBPD extraction changed')
    paths=[receipt,model,Path(__file__).resolve(),Path(__file__).with_name('prototype_capacitance_aliases.py'),Path(__file__).with_name('compare_prototype_analog_devices_v2.py'),Path(__file__).with_name('build_prototype_DCO_rc.py'),Path(__file__).with_name('prepare_prototype_analog_reference.py')]
    pins={str(p):sha(p) for p in paths};text,detail=reduce(model.read_text());target=output/'signal.spice';target.write_text(text)
    report=output/'reduction.json';save(report,detail);verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(target):sha(target),str(report):sha(report)},
        exact_retained_card_and_capacitor_reparse_pass=True,full_vs_reduced_native_waveform_correlation_complete=False,
        diagnostic=True,validated_for_prototype=False,release_ready=False))
    print('Removed fixed-terminal devices:',detail['removed_fixed_terminal_primitives'],'retained:',detail['retained_primitives'])


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);run(p.parse_args().output.resolve())
