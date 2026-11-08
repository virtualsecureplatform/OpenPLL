"""Screen explicit PLLOUT wire R/C scale; never infer active-circuit timing bounds."""
import argparse,heapq,json
from fractions import Fraction as F
from pathlib import Path
from common_v3 import save,sha,verify
from native_spice_comments import strip_floating_annotation
from audit_keeper_native_R_contraction import number


def screen(path):
    graph={};resistors=[]
    with path.open() as stream:
        for line in stream:
            if line[:1].upper()!='R':continue
            _,a,b,value=strip_floating_annotation(line).split();a=a.lower();b=b.lower();value=number(value)
            if value<=0:raise ValueError('positive wire resistors required')
            graph.setdefault(a,[]).append((b,value));graph.setdefault(b,[]).append((a,value));resistors.append(value)
    if 'pllout' not in graph:raise ValueError('PLLOUT wire component required')
    seen={'pllout'};todo=['pllout']
    while todo:
        for b,_ in graph[todo.pop()]:
            if b not in seen:seen.add(b);todo.append(b)
    if seen!=set(graph):raise ValueError('only one PLLOUT wire component supported')
    cap=F(0);intra=F(0);cards=0
    with path.open() as stream:
        for line in stream:
            if line[:1].upper()!='C':continue
            _,a,b,value=strip_floating_annotation(line).split();a=a.lower();b=b.lower()
            if a not in seen and b not in seen:continue
            value=number(value)
            if value<0:raise ValueError('nonnegative explicit capacitance required')
            cap+=value;cards+=value>0
            if a in seen and b in seen:intra+=value
    diameter=F(0);ends=None
    for start in graph:
        dist={start:F(0)};queue=[(F(0),start)]
        while queue:
            d,n=heapq.heappop(queue)
            if dist[n]!=d:continue
            for other,r in graph[n]:
                v=d+r
                if other not in dist or v<dist[other]:dist[other]=v;heapq.heappush(queue,(v,other))
        far=max(dist,key=dist.get)
        if dist[far]>diameter:diameter=dist[far];ends=[start,far]
    return dict(wire_R_cards=len(resistors),wire_R_nodes=len(graph),sum_wire_R_ohm=float(sum(resistors)),maximum_shortest_series_path_R_ohm=float(diameter),diameter_endpoints=ends,incident_positive_explicit_C_cards=cards,incident_explicit_C_F=float(cap),intra_component_explicit_C_F=float(intra),series_path_diameter_times_explicit_C_s=float(diameter*cap),exact_series_path_diameter_ohm=str(diameter),exact_incident_explicit_C_F=str(cap),intrinsic_device_capacitances_included=False,effective_resistance_diameter_computed=False,active_driver_and_load_response_included=False,timing_or_phase_bound_qualified=False,physical_C_mapping_qualified=False,release_ready=False)


def run(control,output):
    receipt=control/'assessment.json';a=json.loads(receipt.read_text());verify(a['artifacts'])
    if not a['charge_conservation_verified'] or not a['contraction']['exact_device_and_C_contraction_verified']:raise ValueError('completed charge-conserving accounting control required')
    circuit=control/'retained_C_control.spice';metrics=screen(circuit);output.mkdir(parents=True,exist_ok=False)
    helpers=[Path(__file__).resolve(),Path(__file__).with_name('native_spice_comments.py'),Path(__file__).with_name('audit_keeper_native_R_contraction.py')]
    save(output/'assessment.json',dict(input_sha256={str(p):sha(p) for p in [receipt,circuit,*helpers]},artifacts={},**metrics,scope='Explicit wire-R and extracted-C screening on an unqualified accounting control; upstream dependency closures are not requalified'))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['control','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.control.resolve(),a.output.resolve())
