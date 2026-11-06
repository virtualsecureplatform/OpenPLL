"""Audit resistor-connected voltage cuts and remaining REFCLK forcing gaps."""
import argparse,json,math
from collections import defaultdict
from pathlib import Path
from common_v3 import save,sha,verify
from compare_prototype_physical_primitive_graphs import Union
from audit_selected_dco_history_inputs import sources


def run(reference,plan,elimination,variation,model,output):
    if output.exists():raise FileExistsError(output)
    p=json.loads(plan.read_text());verify(p['input_sha256'])
    if p['input_sha256'].get(str(model))!=sha(model):raise ValueError('same physical clock-control model required')
    e=json.loads(elimination.read_text());verify(e['input_sha256']);verify(e['artifacts'])
    v=json.loads((variation/'assessment.json').read_text());verify(v['artifacts'])
    if v['input_sha256'].get(str(reference/'sources.spice'))!=sha(reference/'sources.spice'):raise ValueError('same constant-cut reference required')
    # SPICE node names are case-insensitive; the elimination receipt normalizes
    # them while physical routing metadata preserves original spelling.
    excluded={n.lower() for n in e['eliminated_constant_nodes']}|{n.lower() for n in p['prescribed_control_driver_input_nodes']}|{'0','vpwr','vgnd','vpb','vnb'}
    constant={}
    for n,(_,value) in sources(reference/'sources.spice').items():
        try:value=float(value)
        except ValueError:continue
        if not math.isfinite(value):raise ValueError('finite boundary voltage required')
        if n.lower() not in excluded:constant[n]=value
    u=Union();top=[];inside=False;incident=defaultdict(list)
    for line in model.open():
        f=line.split()
        if not f:continue
        if f[0].lower()=='.subckt':inside=f[1]=='IntegerPLL_400MHz_PrototypeTop';top=f[2:] if inside else top;continue
        if f[0].lower()=='.ends':inside=False;continue
        if inside and f[0].startswith('R'):
            if len(f)!=4 or not math.isfinite(float(f[3])) or float(f[3])<=0:raise ValueError('literal positive physical wire resistance required')
            a,b=f[1:3];u.join(a.lower(),b.lower())
            incident[a.lower()].append(f[0]);incident[b.lower()].append(f[0])
    cuts=defaultdict(list)
    for n in p['required_non_supply_boundary_voltage_nodes']:cuts[u.find(n.lower())].append(n)
    clocks=[]
    for n in p['resolved_dynamic_boundary_nodes']:
        connected=cuts[u.find(n.lower())]
        if connected:raise ValueError('resolved clock is resistor-connected to a prescribed cut: '+n)
        clocks.append(dict(node=n,resistive_component_voltage_cuts=connected))
    # Also check every known external output of the added buffer/inverter cells.
    for cell in p['added_clock_driver_cells']:
        pins=cell['pins'];outputs=[pins[k] for k in ['X','Y','Z','Q'] if k in pins]
        if not outputs:raise ValueError('explicit added clock-cell output binding required')
        if any(cuts[u.find(n.lower())] for n in outputs):raise ValueError('added clock output resistor-connected to a prescribed cut')
    rows={r['node'].lower():r for r in json.loads((variation/'boundaries.json').read_text())};records=[]
    for n,held in constant.items():
        if not incident[n.lower()]:raise ValueError('unexplained surviving noncapacitive voltage cut: '+n)
        row=rows[n.lower()];ports=[x for x in top if u.find(x.lower())==u.find(n.lower())]
        records.append(dict(node=n,held_V=held,native_span_V=row['span_V'],incident_wire_resistors=incident[n.lower()],resistively_connected_top_ports=ports))
    records.sort(key=lambda r:r['native_span_V'],reverse=True)
    paths=[plan,elimination,variation/'assessment.json',variation/'boundaries.json',reference/'sources.spice',model,Path(__file__).resolve(),Path(__file__).with_name('compare_prototype_physical_primitive_graphs.py')]
    pins={str(q):sha(q) for q in paths};verify(pins)
    save(output,dict(input_sha256=pins,resolved_clock_checks=clocks,all_added_clock_outputs_without_resistive_voltage_cuts=True,
        remaining_nonrail_nonprogramming_resistive_cuts=records,switching_cuts_above_0p1V=[r for r in records if r['native_span_V']>.1],
        reference_input_sensitivity_qualified=False,frequency_uncertainty_bound_qualified=False,physical_models_qualified=False,release_ready=False))
    print(json.dumps(dict(resolved_clock_nodes_without_resistive_cuts=len(clocks),remaining_resistive_cuts=len(records),switching_cuts=[dict(node=r['node'],span_V=r['native_span_V'],top_ports=r['resistively_connected_top_ports']) for r in records if r['native_span_V']>.1])))

if __name__=='__main__':
    a=argparse.ArgumentParser()
    for n in ['reference','plan','elimination','variation','model','output']:a.add_argument('--'+n,type=Path,required=True)
    p=a.parse_args();run(*(getattr(p,n).resolve() for n in ['reference','plan','elimination','variation','model','output']))
