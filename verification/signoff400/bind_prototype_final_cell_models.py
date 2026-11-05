"""Bind retained cell observations by exact devices and signed C, independent of card ordering."""
import argparse
import json
from pathlib import Path
from common_v3 import save, sha, verify
from prepare_prototype_analog_reference import subcircuits
from prepare_prototype_BBPD_receiver_v2 import header
from compare_prototype_analog_devices_v2 import devices
from audit_hierarchical_capacitance import flatten


def compare(old, new, master):
    if master not in old: return dict(master=master,retained_model_present=False,exact_model_identity=False)
    a,b={master:old[master]},{master:new[master]}
    interface=set(header(old[master]))==set(header(new[master]))
    primitives=devices(a,master)==devices(b,master)
    capacitance=flatten(a,master)[0]==flatten(b,master)[0]
    return dict(master=master,retained_model_present=True,interface_names_match=interface,
                expanded_primitive_cards_match=primitives,complete_signed_C_operator_matches=capacitance,
                exact_model_identity=interface and primitives and capacitance)


def run(retained, extraction, route, output):
    old_receipt=retained/'native_assessment.json';new_receipt=extraction/'assessment.json';rr=route/'assessment.json'
    a,b,r=[json.loads(p.read_text()) for p in (old_receipt,new_receipt,rr)]
    for record in (a,b,r):verify(record['artifacts'])
    old=retained/'IntegerPLL_400MHz_PrototypeTop/capacitance.spice'
    new=extraction/'IntegerPLL_ProgrammedCore/capacitance.spice'
    if b['input_sha256'].get(str(rr))!=sha(rr):raise ValueError('final extraction/route mismatch')
    for p,record in ((old,a),(new,b)):
        if record['artifacts'].get(str(p))!=sha(p):raise ValueError('cell bank changed')
    before,after=[subcircuits(p.read_text()) for p in (old,new)]
    sequential={m for m in r['cell_inventory'] if '__dfrtp_' in m or '__dfstp_' in m}
    if not sequential<=after.keys():raise ValueError('final sequential extraction coverage incomplete')
    rows=[compare(before,after,m) for m in sorted(after) if m.startswith('sky130_fd_sc_')]
    paths=[old_receipt,new_receipt,rr,old,new,Path(__file__).resolve()]
    for n in ('prepare_prototype_analog_reference.py','prepare_prototype_BBPD_receiver_v2.py',
              'compare_prototype_analog_devices_v2.py','audit_hierarchical_capacitance.py'):
        paths.append(Path(__file__).with_name(n))
    pins={str(p):sha(p) for p in paths};verify(pins)
    output.mkdir(parents=True,exist_ok=False);detail=output/'models.json';save(detail,rows)
    matching={x['master'] for x in rows if x['exact_model_identity']}
    save(output/'assessment.json',dict(input_sha256=pins,artifacts={str(detail):sha(detail)},
         compared_final_cell_masters=len(rows),exactly_identical_masters=sorted(matching),
         matched_sequential_masters=sorted(sequential&matching),
         unmatched_sequential_masters=sorted(sequential-matching),
         every_routed_state_master_explicitly_checked=True,
         interface_permutations_and_capacitor_card_order_do_not_change_operator=True,
         final_macro_loading_bound_by_cell_identity=False,native_capture_envelope_qualified=False,
         release_ready=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('retained','extraction','route','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();run(a.retained.resolve(),a.extraction.resolve(),a.route.resolve(),a.output.resolve())
