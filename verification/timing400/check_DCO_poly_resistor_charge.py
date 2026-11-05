#!/usr/bin/env python3
"""Resolve native generic-poly charge accounting against the actual PDK card."""
from decimal import Decimal
import json
from pathlib import Path
import re
import shlex
import time

from compile_local_C_operators_v2 import digest, save


def main():
    root = Path(__file__).resolve().parents[2]
    base = root/'build/timing400/release_001'
    owner = base/'distributed_RC_model_qualification_001/owner.json'
    deadline = json.loads(owner.read_text())['deadline_uptime']
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    model = Path('/opt/pdk/ciel/sky130/versions/1689ac3f2dc763876eaf967227c7dfe831b031ae/sky130A/libs.tech/ngspice/sky130_fd_pr__model__r+c.model.spice')
    text = model.read_text()
    name = 'sky130_fd_pr__res_generic_po'
    blocks = re.findall(r'(?im)^\.subckt\s+'+name+r'\s+([^\n]+)\n(.*?)^\.ends[^\n]*$', text, re.S)
    assert len(blocks) == 1
    header, body = blocks[0]
    assert header.split() == ['t1', 't2', 'w=1', 'l=1']
    cards = [s.strip() for s in body.splitlines() if s.strip() and not s.lstrip().startswith('*')]
    assert cards == ['R0 t1 t2 sky130_fd_pr__res_generic_po w = {w} l = {l}'], cards
    model_cards = [s for s in text.splitlines() if s.lower().startswith('.model '+name+' ')]
    assert len(model_cards) == 1 and model_cards[0].split()[2].lower() == 'r'
    assert not any(re.search(r'\b'+term+r'\s*=', model_cards[0], re.I) for term in ['c', 'cap', 'cj', 'cjsw'])
    top = 'IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8_LOAD36_C1FINE160'
    ext = base/'DCO_R_tile_domain_trace_controls_001/trace'/(top+'.ext')
    lines = [shlex.split(s) for s in ext.read_text().splitlines() if s.strip()]
    resistor_nodes = {f[1]: f for f in lines if f[0] == 'node' and f[6] == 'rmp'}
    assert len(resistor_nodes) == 2
    assert all(Decimal(f[2]) == 50 and Decimal(f[3]) == 0 for f in resistor_nodes.values())
    coupling = [f for f in lines if f[0] == 'cap' and set(f[1:3]) & resistor_nodes.keys() and Decimal(f[3]) != 0]
    assert not coupling
    devices = [f for f in lines if f[0] == 'device' and f[1] == 'rsubckt' and f[2] == name]
    assert len(devices) == 2 and all(sum(n in f for n in resistor_nodes) == 1 for f in devices)
    source = root/'build/timing400/magic_R_tile_domain_source_001/extract/ExtBasic.c'
    source_text = source.read_text()
    assert 'fprintf(outFile, "node \\"%s\\" %d %lg", text, intR, finC);'.replace('\\\\', '\\') in source_text
    assert 'finC = reg->nreg_cap/ExtCurStyle->exts_capScale;' in source_text
    family = base/'DCO_complete_domain_model_primitives_001'
    conns = json.loads((family/'device_connections.json').read_text())
    retained = {n: r for n, r in conns.items() if r['model'] == name}
    assert len(retained) == 2
    for r in retained.values():
        card = r['exact_junction_private_candidate_card']
        assert len(r['private_terminals']) == 2 and card[2:] == [name, 'w=0.48', 'l=0.5']
        assert len(set(r['private_terminals'])) == 2
    out = base/'DCO_poly_resistor_charge_accounting_001'
    out.mkdir(exist_ok=False)
    save(out/'model_and_native_records.json', dict(PDK_subcircuit_header=header, PDK_subcircuit_cards=cards,
        PDK_model=model_cards[0], native_intermediate_nodes=list(resistor_nodes.values()),
        native_resistor_records=devices, retained_device_names=sorted(retained)))
    inputs = [Path(__file__).resolve(), owner, model, ext, source, family/'device_connections.json', family/'assessment.json']
    result = dict(generic_poly_resistor_native_and_PDK_charge_accounting_complete=True,
        native_intermediate_nodes=2, native_intermediate_ground_capacitance=0,
        nonzero_intermediate_pair_capacitors=0, PDK_subcircuit_contains_one_resistor_and_no_charge_elements=True,
        two_finite_original_PDK_devices_and_exact_parameters_retained=True,
        previous_50_capacitance_interpretation_rejected='50 is the native resistance field; the following capacitance field is zero.',
        absolute_silicon_intrinsic_capacitance_bound_claimed=False,
        runtime_model_eligible=False, release_qualified=False, adopted=False, deadline_uptime=deadline,
        input_sha256={str(p.resolve()): digest(p) for p in inputs},
        artifacts={str((out/'model_and_native_records.json').resolve()): digest(out/'model_and_native_records.json')})
    assert time.clock_gettime(time.CLOCK_BOOTTIME) < deadline
    save(out/'assessment.json', result)
    print(json.dumps({k: v for k, v in result.items() if k not in ['input_sha256', 'artifacts']}, indent=2))


if __name__ == '__main__':
    main()
