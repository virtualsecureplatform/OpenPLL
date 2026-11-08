"""Inventory exact linear-boundary reduction opportunities; do not transform or qualify a model."""
import argparse,json
from collections import Counter,defaultdict
from pathlib import Path
from common_v3 import save,sha,verify
from audit_keeper_native_R_contraction import number


def root_cards(model):
    active=False;roots=0
    with model.open() as stream:
        for line in stream:
            fields=line.split()
            if not fields or fields[0].startswith('*'):continue
            if fields[0].lower()=='.subckt':
                if active:raise ValueError('nested conditional root')
                active=not fields[1].startswith('__openpll_');roots+=active;continue
            if fields[0].lower()=='.ends':active=False;continue
            if active:
                if fields[0][0].upper() not in ['C','X','R']:raise ValueError('unsupported top-level conditional card')
                yield fields
    if roots!=1 or active:raise ValueError('one complete conditional root required')


def inventory(model,bindings):
    external={p.lower() for p in bindings['externally_driven_ports'].values()};observed={p.lower() for p in bindings['observation_only_ports'].values()}
    if external&observed:raise ValueError('observation node cannot be externally driven')
    direct=set();cards=Counter()
    for fields in root_cards(model):
        kind=fields[0][0].upper();cards[kind]+=1
        if kind!='C':direct.update({p.lower() for p in fields[1:]}&external)
    cap_only=external-direct;counts=Counter();groups=defaultdict(set)
    for fields in root_cards(model):
        if fields[0][0].upper()!='C':continue
        if len(fields)!=4 or number(fields[3])<=0:raise ValueError('positive literal top-level capacitors required')
        a,b=[p.lower() for p in fields[1:3]]
        if not {a,b}&cap_only:continue
        if a in external|{'0'} and b in external|{'0'}:counts['forced_boundary_only_C']+=1
        else:
            inner=b if a in cap_only else a;boundary=a if a in cap_only else b;groups[inner].add(boundary);counts['boundary_to_interior_C']+=1
    projected_C=cards['C']-counts['forced_boundary_only_C']-counts['boundary_to_interior_C']+len(groups)
    return dict(original_top_level_card_counts=dict(cards),external_ports=len(external),direct_device_or_other_ports=len(direct),capacitor_only_ports=len(cap_only),aggregate_internal_targets=len(groups),forced_boundary_only_C=counts['forced_boundary_only_C'],capacitor_only_boundary_to_interior_C=counts['boundary_to_interior_C'],maximum_distinct_boundary_neighbors_per_target=max(map(len,groups.values()),default=0),projected_forcing_waveforms=len(direct)+len(groups),projected_explicit_C_cards=projected_C,projection_assumptions=['Prescribed ideal boundary voltage histories remain unchanged','Linear constant positive capacitors only','Interior voltages are the observables; eliminated boundary-source currents are not retained'],model_transformed=False,native_equivalence_verified=False,floating_point_aggregation_error_qualified=False,independently_predictive_model_qualified=False,power_qualified=False,release_ready=False)


def run(conditional,output):
    receipt=conditional/'assessment.json';a=json.loads(receipt.read_text());verify(a['artifacts']);model=conditional/'model.spice';binding=conditional/'bindings.json';metrics=inventory(model,json.loads(binding.read_text()));output.mkdir(parents=True,exist_ok=False)
    save(output/'assessment.json',dict(input_sha256={str(p):sha(p) for p in [receipt,model,binding,Path(__file__).resolve(),Path(__file__).with_name('audit_keeper_native_R_contraction.py')]},artifacts={},**metrics))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['conditional','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.conditional.resolve(),a.output.resolve())
