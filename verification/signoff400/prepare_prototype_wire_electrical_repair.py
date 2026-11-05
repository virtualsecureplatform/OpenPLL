"""Admit native-library electrical resizing only for a same-route wire-RC nonpass."""
import argparse
import json
from pathlib import Path
import sys
from common_v3 import ROOT,save,sha,verify
sys.path.insert(0,str(ROOT/'verification/timing400'))
from check_compact_routed_timing import normalize_spef


def run(route,electrical,inventory,obligations,wires,output):
    folders=(route,electrical,inventory,obligations,wires)
    receipts=[p/'assessment.json' for p in folders]
    r,e,i,o,w=[json.loads(p.read_text()) for p in receipts]
    for a in (r,e,i,o,w):verify(a['input_sha256']);verify(a['artifacts'])
    if (not e['all_five_corners_reviewed'] or e['electrical_limits_passed']
            or w['input_sha256'].get(str(route/'route.odb'))!=sha(route/'route.odb')
            or i['input_sha256'].get(str(receipts[0]))!=sha(receipts[0])
            or not w['all_terminal_inventories_match_routed_nominal']):
        raise ValueError('same-route all-corner electrical nonpass and wire views required')
    eq={n:h for n,h in i['input_sha256'].items() if n.endswith('/assessment.json') and 'equivalence' in n}
    for name in e['input_sha256']:
        if name.endswith('/assessment.json') and 'wire_timing_' in name:
            timing=json.loads(Path(name).read_text())
            if any(timing['input_sha256'].get(n)!=h for n,h in eq.items()) or not timing['minmax_wire_RC_used']:
                raise ValueError('electrical reports use another candidate or RC scope')
    chains=json.loads((obligations/'obligations.json').read_text())['synchronizers']
    if len(chains)!=13 or any(c['stages'][0]['routed_master']!='sky130_fd_sc_hs__dfrtp_1' for c in chains):
        raise ValueError('all thirteen first-stage masters must remain characterized DFRTP1')
    fixed=[c['stages'][0]['routed_cell'].lstrip('\\') for c in chains]
    pins={str(p):sha(p) for p in (*receipts,obligations/'obligations.json',wires/'max.spef',
                                electrical/'violations.json',Path(__file__).resolve(),
                                Path(__file__).with_name('common_v3.py'))}
    output.mkdir(parents=True,exist_ok=False)
    target=output/'max.normalized.spef';text,count=normalize_spef((wires/'max.spef').read_text());target.write_text(text)
    pins[str(target)]=sha(target);verify(pins)
    save(output/'plan.json',dict(input_sha256=pins,route_sha256=sha(route/'route.odb'),
        targets=[],branches=[],protected_first_stage_cells=fixed,maximum_wire_spef=str(target),
        normalized_clock_names=count,repair_kind='native_library_slew_and_capacitance',
        setup_frequency_optimization_requested=False,RTL_and_timing_exceptions_unchanged=True,
        independent_equivalence_and_five_corner_minmax_RC_recheck_required=True,release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('route','electrical','inventory','obligations','wires','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(*(getattr(a,n).resolve() for n in ('route','electrical','inventory','obligations','wires','output')))
