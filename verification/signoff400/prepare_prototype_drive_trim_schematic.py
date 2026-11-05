"""Build a seven-inversion static-drive-trim schematic for native range experiments."""
import argparse
import json
from pathlib import Path

from common_v3 import ROOT, save, sha, verify
from prepare_prototype_analog_reference import subcircuits

TOP = 'OpenPLL_DCO_DriveTrim_Schematic'


def build(models, fine_loads):
    if fine_loads <= 0 or fine_loads % 255:
        raise ValueError('whole copies of every fine control required')
    statements = []
    def cell(name, model, **signals):
        block = models[model]
        header = block.splitlines()[0].split()[2:]
        values = []
        rails = dict(VPWR='VPWR', VGND='VGND', VPB='VPB', VNB='VNB')
        for index, pin in enumerate(header):
            if pin in signals:
                values.append(signals[pin])
            elif pin in rails:
                values.append(rails[pin])
            elif pin.startswith('a_'):
                values.append(f'{name}_private_{index}')
            else:
                raise ValueError('unbound functional cell pin: '+model+'/'+pin)
        if set(signals)-set(header):
            raise ValueError('unknown cell signal pin')
        statements.append('X'+name+' '+' '.join(values)+' '+model)
    hd = 'sky130_fd_sc_hd__'
    cell('reset_gate', hd+'nand2_8', A='ring6', B='RESET_N', Y='ring0')
    for bit in range(47):
        cell(f'coarse_invert_{bit}', hd+'einvp_1', TE='VPWR',
             A=f'COARSETHERMAL_CODE[{bit}]', Z=f'disable_{bit}')
    for stage in range(1, 7):
        cell(f'baseline_{stage}', hd+'einvn_0', TE_B='VGND', A=f'ring{stage-1}', Z=f'ring{stage}')
        for bit in range(47):
            cell(f'boost_{stage}_{bit}', hd+'einvn_0', TE_B=f'disable_{bit}',
                 A=f'ring{stage-1}', Z=f'ring{stage}')
    for index in range(fine_loads):
        bit = 255*index//fine_loads
        cell(f'fine_{index}', hd+'einvp_1', TE=f'DCO_THERM[{bit}]',
             A=f'ring{1+index%6}', Z=f'fine_unused_{index}')
    cell('output', hd+'buf_8', A='ring0', X='PLLOUT')
    ports = ['RESET_N', 'PLLOUT', 'VPWR', 'VGND', 'VPB', 'VNB']
    ports += [f'COARSETHERMAL_CODE[{i}]' for i in range(47)]
    ports += [f'DCO_THERM[{i}]' for i in range(255)]
    return ('* Schematic architecture experiment: cell C only, no routed intercell R/C or parent loads.\n'
            +'\n'.join(models.values())+'\n.subckt '+TOP+' '+' '.join(ports)+'\n'
            +'\n'.join(statements)+'\n.ends '+TOP+'\n')


def run(cells, geometry, output, fine_loads):
    receipt = cells/'assessment.json'; checked = json.loads(receipt.read_text())
    verify(checked['input_sha256']); verify(checked['artifacts'])
    if not checked['schematic_architecture_experiments_eligible'] or not checked['wrong_width_negative_control_rejected']:
        raise ValueError('checked isolated drive cells required')
    geometry_receipt = geometry/'assessment.json'
    previous = json.loads(geometry_receipt.read_text()); verify(previous['input_sha256']); verify(previous['artifacts'])
    if not previous['all_cell_primitive_geometry_features_match'] or not previous['all_cell_capacitance_networks_passive']:
        raise ValueError('checked source cell models required')
    original = next(Path(p) for p in previous['input_sha256'] if p.endswith('/nom.spice'))
    blocks = subcircuits(original.read_text())
    selected = {name: blocks[name] for name in ('sky130_fd_sc_hd__nand2_8', 'sky130_fd_sc_hd__einvp_1', 'sky130_fd_sc_hd__buf_8')}
    source = next(Path(p) for p in checked['input_sha256'] if p.endswith('/sky130_fd_sc_hd__einvn_0/capacitance.spice'))
    selected.update(subcircuits(source.read_text()))
    if set(selected) != {'sky130_fd_sc_hd__nand2_8', 'sky130_fd_sc_hd__einvp_1', 'sky130_fd_sc_hd__buf_8', 'sky130_fd_sc_hd__einvn_0'}:
        raise ValueError('unexpected architecture cell inventory')
    output.mkdir(parents=True, exist_ok=False)
    model = output/'schematic.spice'; model.write_text(build(selected, fine_loads))
    inputs = [receipt, geometry_receipt, original, source, Path(__file__).resolve()]
    save(output/'assessment.json', dict(input_sha256={str(p): sha(p) for p in inputs},
         artifacts={str(model): sha(model)}, top=TOP, schematic_only=True,
         fine_loads=fine_loads, controlled_inverting_stages=6,
         always_enabled_units_per_stage=1, thermometer_enabled_units_per_stage=47,
         coarse_code_increases_drive=True, fixed_reset_inversion_stages=1,
         intercell_RC_and_parent_loading_included=False, architecture_selected=False,
         analog_tuning_qualified=False, release_ready=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('cells', 'geometry', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--fine-loads', type=int, default=1020)
    args = parser.parse_args()
    run(args.cells.resolve(), args.geometry.resolve(), args.output.resolve(), args.fine_loads)
