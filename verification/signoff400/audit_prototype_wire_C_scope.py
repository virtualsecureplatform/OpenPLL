"""Inventory hierarchical interaction capacitance involving cell-internal conductor ports."""
import argparse,json,re
from fractions import Fraction as F
from pathlib import Path
from common_v3 import save,sha,verify
from prepare_prototype_analog_reference import subcircuits
from prepare_prototype_BBPD_receiver_v2 import header
from bind_prototype_spef_pins_v2 import hierarchy
from audit_hierarchical_capacitance import number


def run(source,top,output):
    text=source.read_text();blocks=subcircuits(text);ports,instances,canonical=hierarchy(text,top)
    private=set();functional=set();private_ports=0
    for instance in instances.values():
        for pin,node in instance['pins'].items():
            if re.fullmatch(r'a_\d+_\d+#',pin):private.add(canonical(node));private_ports+=1
            else:functional.add(canonical(node))
    exclusive=private-functional;rows=[]
    for line in blocks[top].splitlines():
        if line.startswith('+'):rows[-1]+=' '+line[1:]
        elif line.strip():rows.append(line)
    groups={kind:dict(count=0,positive=F(),negative=F()) for kind in ('exclusive_cell_internal_endpoint','functional_or_supply_only')}
    for row in rows:
        f=row.split()
        if not f or f[0][0].upper()!='C':continue
        if len(f)!=4:raise ValueError('constant two-terminal interaction capacitor required')
        value=number(f[3]);kind='exclusive_cell_internal_endpoint' if any(canonical(n) in exclusive for n in f[1:3]) else 'functional_or_supply_only'
        g=groups[kind];g['count']+=1;g['positive' if value>=0 else 'negative']+=value
    report={kind:dict(count=g['count'],positive_sum_F=str(g['positive']),negative_sum_F=str(g['negative']),absolute_sum_F=str(g['positive']-g['negative'])) for kind,g in groups.items()}
    output.mkdir(parents=True,exist_ok=False);detail=output/'scope.json';save(detail,dict(top=top,cell_internal_interface_ports=private_ports,exclusive_internal_conductors=len(exclusive),interaction_capacitance=report))
    pins={str(p):sha(p) for p in (source,Path(__file__).resolve(),Path(__file__).with_name('bind_prototype_spef_pins_v2.py'),Path(__file__).with_name('audit_hierarchical_capacitance.py'))};verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(detail):sha(detail)},
        cell_internal_interaction_capacitors=groups['exclusive_cell_internal_endpoint']['count'],
        wire_only_SPEF_replacement_requires_independent_correlation=True,omitted_interaction_error_bounded=False,
        original_signed_capacitances_unchanged=True,validated_for_prototype=False,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',required=True,type=Path);p.add_argument('--top',required=True);p.add_argument('--output',required=True,type=Path)
    a=p.parse_args();run(a.source.resolve(),a.top,a.output.resolve())
