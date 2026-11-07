"""Build an isolated four-load RTL proposal from the measured physical lineage."""
import argparse
import json
from pathlib import Path
from common_v3 import ROOT, save, sha, verify


def run(output):
    base = ROOT/'build/signoff400'
    routed = base/'prototype_v3_DCO_fine_grain_high_candidate_001'
    source = routed/'config/dco_fine_grain_high255.v'
    mapping = base/'selected_checkpoint_history_load_cells_1068/assessment.json'
    wires = base/'prototype_v3_selected_context_clock_wire_joint_wire_R_margin20_nom_driver_019/wire_map.json'
    model = base/'prototype_v3_Xyce_full_C_programming_pilot_030/model.spice'
    pair = base/'selected_checkpoint_external_keeper_IC_pair_1091/assessment.json'
    parent = ROOT/'build/signoff400/prototype_v3_selected_parent_filled_layout_019/assessment.json'
    pnl = routed/'config/runs/prototype_fine_grain_high255_001/final/pnl/IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8_LOAD36_C1FINE160.pnl.v'
    manifest = json.loads((routed/'input_manifest.json').read_text())
    verify({str(source): manifest['input_sha256'][str(source)]})
    layout = json.loads(parent.read_text())
    verify({str(pnl): layout['input_sha256'][str(pnl)]})
    evidence = json.loads(pair.read_text())
    verify(evidence['input_sha256']); verify(evidence['artifacts'])
    if not evidence['both_native_cases_completed_normally']:
        raise ValueError('completed keeper pair required')
    parents = {}
    def find(x):
        while x in parents:
            x = parents[x]
        return x
    for line in model.open():
        fields = line.lower().split()
        if fields and fields[0].startswith('r') and len(fields) >= 4:
            x, y = find(fields[1]), find(fields[2])
            if x != y:
                parents[x] = y
    junctions = json.loads(wires.read_text())['shared_macro_access_junctions']
    cells = json.loads(mapping.read_text())['cells']
    expected = {'404': (95, 191, 2), '405': (97, 195, 2),
                '441': (96, 192, 1), '515': (111, 223, 2)}
    if len(cells) != 4:
        raise ValueError('four measured cells required')
    text = source.read_text(); additions = []; records = []
    for cell in cells:
        suffix = cell['cell'].rsplit('_', 1)[1]
        bit, load, ring = expected[suffix]
        te = cell['local_to_native_nodes']['TE'].lower()
        ports = [j for j in junctions if find(j['junction'].lower()) == find(te)]
        if len(ports) != 1 or ports[0]['accesses'][0] != [f'child::DCO_THERM[{bit}]', f'DCO_THERM[{bit}]']:
            raise ValueError('measured enable conductor mismatch')
        line = (f'    (* keep, dont_touch *) sky130_fd_sc_hd__einvp_1 fine_{load} '
                f'(`INTEGERPLL_SKY130_CELL_PG .A(ring[{ring}]), .TE(DCO_THERM[{bit}]), .Z(unused_load[{load}]));')
        if text.count(line) != 1:
            raise ValueError('frozen source load mismatch')
        additions += [f'    wire history_enable_b_{load};',
            f'    (* keep, dont_touch *) sky130_fd_sc_hs__inv_2 history_enable_{load} (`INTEGERPLL_SKY130_CELL_PG .A(DCO_THERM[{bit}]), .Y(history_enable_b_{load}));',
            f'    (* keep, dont_touch *) sky130_fd_sc_hd__einvp_1 history_keeper_{load} (`INTEGERPLL_SKY130_CELL_PG .A(tie_lo), .TE(history_enable_b_{load}), .Z(unused_load[{load}]));']
        records.append(dict(physical_cell=cell['cell'], rtl_instance=f'fine_{load}',
                            enable_bit=bit, signal=f'ring[{ring}]', output=f'unused_load[{load}]'))
    if text.count('\nendmodule') != 1:
        raise ValueError('one isolated macro required')
    output.mkdir(parents=True, exist_ok=False)
    candidate = output/'dco_history_keeper.v'
    candidate.write_text(text.replace('\nendmodule', '\n// Four-load external-pin keeper proposal; extracted qualification pending.\n'+'\n'.join(additions)+'\n\nendmodule'))
    pins = {str(p): sha(p) for p in [source, mapping, wires, model, pair, parent, pnl, routed/'input_manifest.json', Path(__file__).resolve()]}
    save(output/'assessment.json', dict(input_sha256=pins, artifacts={str(candidate):sha(candidate)},
        mapped_loads=records, original_source_retained_except_appended_cells=True,
        added_standard_cells={'sky130_fd_sc_hd__einvp_1':4,'sky130_fd_sc_hs__inv_2':4},
        selected_design_changed=False, physical_layout_qualified=False,
        extracted_parasitics_qualified=False, release_ready=False))


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--output', type=Path, required=True)
    run(p.parse_args().output.resolve())
