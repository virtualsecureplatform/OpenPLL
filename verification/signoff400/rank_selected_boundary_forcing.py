"""Rank omitted native voltage forcing directly into retained DCO unknowns."""
import argparse,json,math
from collections import defaultdict
from pathlib import Path
from common_v3 import save,sha,verify
from audit_selected_dco_history_inputs import sources


def run(observation,reference,output):
    output.mkdir(parents=True,exist_ok=False)
    a=json.loads((observation/'assessment.json').read_text());verify(a['artifacts'])
    if json.loads((observation/'status.json').read_text())['state']!='native_boundary_variation_measured':raise ValueError('complete native boundary statistics required')
    for name in ['manifest.json','sources.spice','devices.spice']:
        if a['input_sha256'].get(str(reference/name))!=sha(reference/name):raise ValueError('same reduced circuit required')
    rows=json.loads((observation/'boundaries.json').read_text());quiet={r['node'] for r in rows}
    # A capacitor between two prescribed voltages changes source currents, not
    # the voltage equations of retained unknowns. Exclude every prescribed cut,
    # including the moving programming/reset sources, from the opposite end.
    prescribed=set(sources(reference/'sources.spice'))|{'0','VPWR','VGND','VPB','VNB'}
    weights=defaultdict(list)
    for line in (reference/'devices.spice').open():
        f=line.split()
        if len(f)!=4 or not f[0].lower().startswith('c'):continue
        c=abs(float(f[3]))
        if not math.isfinite(c):raise ValueError('finite literal C required')
        for n,other in [(f[1],f[2]),(f[2],f[1])]:
            if n in quiet and other not in prescribed:weights[n].append(c)
    duration=(a['measurement_window_ns'][1]-a['measurement_window_ns'][0])*1e-9
    for r in rows:
        c=math.fsum(weights[r['node']]);r['absolute_C_to_retained_voltage_unknowns_F']=c
        r['omitted_boundary_forcing_absolute_charge_C']=c*r['total_variation_V']
        r['omitted_boundary_forcing_average_absolute_current_A']=c*r['total_variation_V']/duration
        r.pop('absolute_C_to_retained_nongrounded_nodes_F',None);r.pop('capacitance_weighted_variation_C',None)
    rows.sort(key=lambda r:r['omitted_boundary_forcing_absolute_charge_C'],reverse=True)
    save(output/'boundaries.json',rows)
    paths=[observation/'assessment.json',observation/'boundaries.json',reference/'sources.spice',reference/'devices.spice',Path(__file__).resolve(),Path(__file__).with_name('audit_selected_dco_history_inputs.py')]
    pins={str(p):sha(p) for p in paths};verify(pins)
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(output/'boundaries.json'):sha(output/'boundaries.json')},
        measurement_window_ns=a['measurement_window_ns'],constant_boundary_nodes=len(rows),
        directly_capacitive_boundary_nodes=sum(r['absolute_C_to_retained_voltage_unknowns_F']>0 for r in rows),
        directly_capacitive_nodes_with_span_above_0p1V=sum(r['absolute_C_to_retained_voltage_unknowns_F']>0 and r['span_V']>.1 for r in rows),
        top_omitted_boundary_voltage_forcing=rows[:20],
        forcing_scope='sum of absolute literal C times native boundary total variation; opposite endpoints must be retained voltage unknowns',
        full_boundary_forcing_replayed=False,frequency_error_causality_demonstrated=False,
        frequency_uncertainty_bound_qualified=False,physical_models_qualified=False,release_ready=False))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['observation','reference','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve() for n in ['observation','reference','output']))
