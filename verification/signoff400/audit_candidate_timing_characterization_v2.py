"""Reconcile the repaired candidate with all completed raw 15-PVT grids."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
from common import save,sha


def run(output):
    output.mkdir(parents=True,exist_ok=False);root=Path.cwd();base=root/'build/timing400/release_001'
    candidate=root/'build/signoff400/startup_corrected_timing_repair_003';proof=candidate/'assessment.json'
    netlist=candidate/'route.v';masters=candidate/'masters.txt';requirements=root/'verification/signoff400/requirements.json'
    campaigns=[base/n/'assessment.json' for n in ('compact_nominal_15PVT_completion_001','compact_sequential_15PVT_completion_001')]
    templates=[base/'compact_propagation_tt27_001/plan.json',base/'compact_sequential_propagation_fs125_001/plan.json']
    supplement=root/'build/signoff400/startup_timing_mux2_4_15PVT_raw_001/assessment.json'
    extra=json.loads(supplement.read_text())
    if extra['completed_raw_PVT_points']!=15 or not extra['all_raw_fixture_events_pass']:raise ValueError('complete passing mux2_4 grid required')
    if extra['input_sha256'][str(netlist)]!=sha(netlist):raise ValueError('supplement measured a different candidate')
    campaigns.append(supplement);templates.append(supplement.parent/'tt_27/plan.json')
    paths=[proof,netlist,masters,requirements,*campaigns,*templates,Path(__file__).resolve()];pins={str(p):sha(p) for p in paths}
    p=json.loads(proof.read_text())
    for path in (netlist,masters):
        if p['artifacts'][str(path)]!=pins[str(path)]:raise ValueError('current routed candidate inventory changed')
    counts=Counter(re.findall(r'^\s*(sky130_fd_sc_hs__\w+)\s+(?:\\\S+|\w+)\s*\(',netlist.read_text(),re.M))
    if counts!=Counter(masters.read_text().split()):raise ValueError('netlist and ODB master inventories differ')
    spec=json.loads(requirements.read_text());expected={(c,t) for c in spec['corners'] for t in spec['temperatures_c']}
    coverage=[]
    for campaign,template in zip(campaigns,templates):
        a=json.loads(campaign.read_text());fixtures=json.loads(template.read_text())['fixtures'];points=set()
        for item in a.get('reused_completed_points',[])+a['case_results']:
            receipt=Path(item['assessment']);plan=Path(item['plan']) if 'plan' in item else receipt.parent.parent/'plan.json'
            if sha(receipt)!=item['assessment_sha256']:raise ValueError('retained case receipt changed')
            r=json.loads(receipt.read_text());s=json.loads(plan.read_text());pv=s['pvt']
            if pv['supply_v']!=1.8 or s['fixtures']!=fixtures:raise ValueError('retained point fixture/supply mismatch')
            if r['fixtures']!=len(fixtures) or r['passing']!=len(fixtures) or not r['all_native_waveform_events_terminal']:raise ValueError('retained raw propagation case incomplete')
            point=(pv['corner'],pv['temperature_c'])
            if point in points:raise ValueError('duplicate retained PVT point')
            points.add(point);pins[str(receipt)]=sha(receipt);pins[str(plan)]=sha(plan)
        if points!=expected:raise ValueError('retained raw PVT coverage differs from requirements')
        coverage.append({r['master'] for r in fixtures})
    combinational,sequential,additional=coverage
    if additional!={'sky130_fd_sc_hs__mux2_4'} or additional & (combinational|sequential):raise ValueError('supplement master identity or duplicate campaign')
    combinational |= additional
    auxiliary_families={'fill','tapvpwrvgnd','decap','conb','diode'}
    auxiliaries={name:count for name,count in counts.items() if name.split('__')[1].rsplit('_',1)[0] in auxiliary_families}
    logic=set(counts)-set(auxiliaries);missing=sorted(logic-combinational-sequential)
    rows={name:dict(instances=count,raw_combinational_15PVT=name in combinational,raw_sequential_propagation_15PVT=name in sequential,
                   auxiliary_without_ordinary_propagation_arc=name in auxiliaries) for name,count in counts.items()}
    save(output/'master_coverage.json',rows)
    if any(sha(Path(name))!=digest for name,digest in pins.items()):raise ValueError('source changed during characterization coverage audit')
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(output/'master_coverage.json'):sha(output/'master_coverage.json')},
         current_route_and_ODB_master_counts_independently_reconciled=True,total_instances=sum(counts.values()),distinct_masters=len(counts),
         distinct_logic_masters=len(logic),logic_masters_with_retained_raw_15PVT=len(logic&(combinational|sequential)),
         required_raw_PVT_points=len(expected),all_candidate_logic_masters_have_raw_15PVT_propagation=not missing,missing_raw_logic_masters=missing,auxiliary_master_counts=auxiliaries,
         raw_propagation_observations_are_not_qualified_timing_views=True,final_fill_and_boundary_loads_qualified=False,
         sequential_constraints_qualified=False,nominal_15PVT_qualified=False,digital_timing_qualified=False,release_qualified=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);run(p.parse_args().output.resolve())
