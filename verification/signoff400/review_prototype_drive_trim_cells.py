"""Check isolated drive-trim cell models before schematic architecture experiments."""
import argparse
from fractions import Fraction as F
import json
from pathlib import Path
import re
import time

from common_v3 import save, sha, verify
from compiled_charge import execute
from resources import lease
from prepare_prototype_analog_reference import subcircuits
from check_prototype_cell_geometry_conversion_v2 import extracted_features, spice_features
from check_prototype_junction_conversion_v3 import inventory, match
from check_prototype_capacitance_paths import certify
from audit_hierarchical_capacitance import flatten
from extract_prototype_analog_capacitance_v2 import PDK

NETGEN = Path('/nix/store/kw3frc6fbv3zi2m9n0wv93y1nfiyjiy6-netgen-1.5.316/bin/netgen')


def run(source, output):
    receipt = source/'native_assessment.json'
    native = json.loads(receipt.read_text())
    verify(native['input_sha256']); verify(native['artifacts'])
    output.mkdir(parents=True, exist_ok=False)
    deadline = time.clock_gettime(time.CLOCK_BOOTTIME)+43200
    reference = PDK/'libs.ref/sky130_fd_sc_hd/spice/sky130_fd_sc_hd.spice'
    setup = PDK/'libs.tech/netgen/sky130A_setup.tcl'
    inputs = [receipt, reference, setup, NETGEN, Path(__file__).resolve()]
    results = []
    names = ['sky130_fd_sc_hd__einvn_0', 'sky130_fd_sc_hd__einvn_1', 'sky130_fd_sc_hd__ebufn_1']
    def lvs(name, model, label):
        script = output/(label+'.tcl'); log = output/(label+'.lvs.log')
        script.write_text(f'readnet spice {model} 1\nreadnet spice {reference} 2\nlvs {{{name} 1}} {{{name} 2}} {setup} {log} -json\nquit\n')
        with lease(1, 4, deadline):
            execute([NETGEN, '-batch', 'source', script], output/(label+'.native.log'), deadline, 4)
        return log.read_text()
    for name in names:
        model = source/name/'capacitance.spice'; ext = source/name/(name+'.ext')
        if any(native['artifacts'].get(str(p)) != sha(p) for p in (model, ext)):
            raise ValueError('unpinned cell extraction')
        blocks = subcircuits(model.read_text())
        if set(blocks) != {name}:
            raise ValueError('one isolated standard-cell model required')
        grid = F(1, 200)
        if extracted_features(ext.read_text(), grid) != spice_features(blocks[name]):
            raise ValueError('cell primitive geometry conversion mismatch')
        raw, converted = inventory(ext.read_text(), blocks[name], grid)
        if any(match(raw[k], converted[k]) is None for k in raw.keys() | converted.keys()):
            raise ValueError('cell junction conversion mismatch')
        certificate = certify(flatten(blocks, name)[0])
        if not certificate['passivity_certified']:
            raise ValueError('cell capacitor passivity not certified')
        mos = output/(name+'.mos.spice')
        mos.write_text('\n'.join(line for line in blocks[name].splitlines() if not line.startswith('C'))+'\n')
        text = lvs(name, mos, name)
        if 'Circuits match uniquely.' not in text or 'Property errors were found' in text:
            raise ValueError('cell transistor LVS mismatch')
        inputs.extend([model, ext])
        results.append(dict(master=name, geometry_and_junction_conversion_checked=True,
                            cell_capacitors_passive=True, transistor_topology_and_width_length_LVS_pass=True))
    negative = output/'negative_width.spice'
    text, count = re.subn(r'\bw=([0-9.]+)', lambda m: 'w='+str(float(m[1])*2),
                         (output/(names[0]+'.mos.spice')).read_text(), count=1)
    if count != 1:
        raise ValueError('negative width mutation missing')
    negative.write_text(text)
    if 'Property errors were found' not in lvs(names[0], negative, 'negative_width'):
        raise ValueError('wrong-width model was not rejected')
    detail = output/'cells.json'; save(detail, results)
    pins = {str(p): sha(p) for p in inputs}; verify(pins)
    save(output/'assessment.json', dict(input_sha256=pins,
         artifacts={str(p): sha(p) for p in output.iterdir() if p.is_file()},
         checked_isolated_masters=names, wrong_width_negative_control_rejected=True,
         schematic_architecture_experiments_eligible=True,
         complete_intercell_RC_or_parent_loads_included=False,
         architecture_selected=False, analog_tuning_qualified=False, release_ready=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    run(args.source.resolve(), args.output.resolve())
