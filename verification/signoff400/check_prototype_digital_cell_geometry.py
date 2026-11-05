"""Check every final digital cell's native geometry against its raw extraction."""
import argparse
from collections import Counter
from fractions import Fraction as F
import json
from pathlib import Path
from common_v3 import save, sha, verify
from prepare_prototype_analog_reference import subcircuits
from check_prototype_cell_geometry_conversion_v2 import extracted_features, spice_features
from check_prototype_junction_conversion_v3 import inventory, match


def run(extraction, joined, converted, output):
    receipts = [p / 'assessment.json' for p in (extraction, joined, converted)]
    e, j, c = [json.loads(p.read_text()) for p in receipts]
    for r in (e, j, c):
        verify(r['input_sha256']); verify(r['artifacts'])
    source = extraction / 'IntegerPLL_ProgrammedCore/capacitance.spice'
    model = converted / 'ng47.spice'
    if c['input_sha256'].get(str(source)) != sha(source):
        raise ValueError('diode conversion source mismatch')
    if not c['exact_expanded_conversion_reparse_pass']:
        raise ValueError('full primitive conversion proof required')
    top_ext = source.parent / 'IntegerPLL_ProgrammedCore.ext'
    if j['input_sha256'].get(str(top_ext)) != sha(top_ext):
        raise ValueError('independent grid belongs to another extraction')
    grid = F(j['magic_grid_um'])
    original = subcircuits(source.read_text()); native = subcircuits(model.read_text())
    if original.keys() != native.keys():
        raise ValueError('converted hierarchy changed')
    paths = [*receipts, source, model, top_ext, Path(__file__).resolve()]
    for name in ('check_prototype_cell_geometry_conversion_v2.py',
                 'check_prototype_junction_conversion_v3.py',
                 'prepare_prototype_analog_reference.py'):
        paths.append(Path(__file__).with_name(name))
    results = []
    for master, block in sorted(original.items()):
        if not master.startswith('sky130_fd_sc_'): continue
        ext = source.parent / (master + '.ext')
        if e['artifacts'].get(str(ext)) != sha(ext):
            raise ValueError('raw cell extraction changed')
        raw = extracted_features(ext.read_text(), grid)
        if raw != spice_features(block):
            raise ValueError('raw geometry conversion mismatch: ' + master)
        expected = Counter()
        for feature, count in raw.items():
            if feature[1] == 'area_perim':
                feature = (*feature[:2], str(F(feature[2]) / 10**12),
                           str(F(feature[3]) / 10**6))
            expected[feature] += count
        if expected != spice_features(native[master]):
            raise ValueError('effective ng47 geometry mismatch: ' + master)
        before, after = inventory(ext.read_text(), native[master], grid)
        if any(match(before[k], after[k]) is None for k in before.keys() | after.keys()):
            raise ValueError('MOS junction conversion mismatch: ' + master)
        paths.append(ext)
        results.append(dict(master=master, primitive_geometry_features=raw.total(),
                            exact_geometry_match=True, MOS_junction_rounding_match=True))
    if not results: raise ValueError('no extracted standard cells')
    pins = {str(p): sha(p) for p in paths}; verify(pins)
    output.mkdir(parents=True, exist_ok=False)
    detail = output / 'masters.json'; save(detail, results)
    save(output / 'assessment.json', dict(input_sha256=pins,
         artifacts={str(detail): sha(detail)}, standard_cell_masters=len(results),
         all_primitive_geometry_features_match=True,
         all_MOS_junction_attributes_match_native_rounding=True,
         ng47_diode_effective_units_match_raw_extraction=True,
         expanded_primitive_instances=c['expanded_primitive_instances'],
         expanded_diodes=c['expanded_diodes'], independent_grid_um=str(grid),
         native_electrical_model_correlation_complete=False,
         independent_diffusion_polygon_geometry_proved=False, release_ready=False))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for n in ('extraction', 'join', 'converted', 'output'):
        p.add_argument('--' + n, type=Path, required=True)
    a = p.parse_args(); run(a.extraction.resolve(), a.join.resolve(),
                           a.converted.resolve(), a.output.resolve())
