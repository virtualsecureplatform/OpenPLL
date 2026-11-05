#!/usr/bin/env python3
"""Emit unqualified private-node device primitives with exact local junction A/P.

Original cards remain preserved in metadata. No distributed C, external feed or
runtime-model eligibility is inferred from exact device junction geometry.
"""
from decimal import Decimal
import json
import math
from pathlib import Path
import signal
import time
from check_compact_clock_tree import verify
from run_dco_qualification import ROOT, sha, save


def main():
    base = ROOT/'build/timing400/release_001'
    owner = base/'distributed_RC_model_qualification_001/owner.json'
    left = json.loads(owner.read_text())['deadline_uptime']-time.clock_gettime(time.CLOCK_BOOTTIME)
    assert left > 0
    signal.alarm(max(1, math.floor(left)))
    geometry = base/'DCO_all_junction_region_audit_001/assessment.json'
    g = verify(geometry)
    assert g['all_local_junction_region_shares_match_GDS']
    assert g['total_junction_area_perimeter_exact_GDS_conservation_passed']
    candidate = base/'DCO_local_decap_junction_candidate_001/device_connections_candidate.json'
    device_rows = json.loads(candidate.read_text())
    junction_path = geometry.parent/'terminal_regions.json'
    junctions = json.loads(junction_path.read_text())
    exact = {}
    rounding = []
    for row in junctions:
        keys = ['as', 'ps'] if row['native_terminal_code'] == 2 else ['ad', 'pd']
        name = row['device']
        device = device_rows[name]
        prior = device.get('junction_corrected_candidate_card', device['original_card'])
        params = dict(v.split('=', 1) for v in prior[5:])
        for key, value, scale in zip(keys, row['local_area_perimeter_internal'], [Decimal('.000025'), Decimal('.005')]):
            physical = Decimal(value)*scale
            exact[name, key] = physical
            delta = abs(Decimal(params[key])-physical)
            if delta:
                rounding.append(dict(device=name, parameter=key, previous_value=params[key],
                    exact_value=str(physical), absolute_difference=str(delta),
                    relative_difference=str(delta/physical)))
    assert len(exact) == 34472
    out = base/'DCO_exact_junction_device_primitives_001'
    out.mkdir(exist_ok=False)
    deck = out/'devices_unqualified.spice'
    with deck.open('x') as stream:
        stream.write('* Unqualified private-node device primitives; exact GDS-backed local MOS junction geometry.\n')
        for name, device in device_rows.items():
            terminals = device['private_terminals']
            original = device['original_card']
            nterm = len(terminals)
            card = list(original)
            if nterm == 4:
                found = set()
                for index, token in enumerate(card[5:], 5):
                    key = token.split('=', 1)[0]
                    if (name, key) in exact:
                        card[index] = key+'='+format(exact[name, key], 'f')
                        found.add(key)
                assert found == {'as', 'ps', 'ad', 'pd'}
            else:
                assert nterm == 2 and device['model'] == 'sky130_fd_pr__res_generic_po'
            assert card[nterm] == device['model']
            card[:nterm] = terminals
            device['exact_junction_private_candidate_card'] = card
            device['runtime_model_eligible'] = False
            stream.write(name+' '+' '.join(card)+'\n')
    # Read the emitted primitive independently: reject omitted AP precision and
    # preserve every non-junction parameter and private terminal connection.
    seen = set()
    for line in deck.open():
        if line.startswith('*'):
            continue
        name, *card = line.split()
        assert name not in seen
        seen.add(name)
        device = device_rows[name]
        nterm = len(device['private_terminals'])
        original = device['original_card']
        assert card[:nterm] == device['private_terminals'] and card[nterm] == original[nterm]
        before = dict(t.split('=', 1) for t in original[nterm+1:])
        after = dict(t.split('=', 1) for t in card[nterm+1:])
        assert before.keys() == after.keys()
        for key, value in before.items():
            if (name, key) in exact:
                assert Decimal(after[key]) == exact[name, key]
            else:
                assert after[key] == value
    assert seen == device_rows.keys() and len(seen) == 8620
    save(out/'device_connections_candidate.json', device_rows)
    save(out/'removed_print_rounding.json', rounding)
    inputs = [Path(__file__).resolve(), owner, geometry, candidate, junction_path]
    artifacts = [deck, out/'device_connections_candidate.json', out/'removed_print_rounding.json']
    max_relative = max(Decimal(r['relative_difference']) for r in rounding)
    save(out/'assessment.json', dict(input_sha256={str(p): sha(p) for p in inputs},
        artifacts={str(p): sha(p) for p in artifacts}, emitted_private_device_primitives=8620,
        MOS_devices_with_exact_local_junction_parameters=8618, exact_junction_parameter_values=34472,
        corrected_missing_decap_sources=152, previous_rounded_parameter_values=len(rounding),
        maximum_removed_relative_print_rounding=str(max_relative),
        exact_AP_private_connections_and_all_other_parameters_checked_in_emitted_deck=True,
        original_cards_retained_unchanged_in_metadata=True,
        distributed_C_external_feeds_nonlinear_charge_and_runtime_error_qualified=False,
        runtime_model_eligible=False, release_qualified=False, adopted=False))
    print('Emitted8620 private device primitives with34472 exact local junction parameters; removed',
          len(rounding), 'rounded parameter values; maximum previous relative error', str(max_relative))


if __name__ == '__main__':
    main()
