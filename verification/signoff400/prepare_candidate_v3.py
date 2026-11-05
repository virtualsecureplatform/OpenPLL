#!/usr/bin/env python3
"""Prepare current-source signoff against an explicit, checked filled candidate."""
import argparse
import json
from pathlib import Path
from common_v2 import ROOT, PROFILE, cases, save, sha, source_pins, verify
from audit_v2 import audit


def prepare(closure, output):
    closure, out = Path(closure).resolve(), Path(output).resolve()
    receipt_path = closure / 'assessment.json'
    receipt = json.loads(receipt_path.read_text())
    verify(receipt['input_sha256']); verify(receipt['artifacts'])
    for flag in ('filled_geometry_checks_pass', 'assembled_drc_pass', 'assembled_lvs_pass',
                 'complete_port_connectivity_screen_passed', 'stock_density_checks_passed'):
        if receipt.get(flag) is not True:
            raise ValueError('geometry prerequisite missing: ' + flag)
    if receipt.get('forming_antenna_violations') != 0 or receipt.get('native_antenna_feedback') != 0:
        raise ValueError('antenna checks have not passed')
    layout = (closure / 'layout').resolve()
    layout_path = layout / 'assessment.json'
    if receipt['input_sha256'].get(str(layout_path)) != sha(layout_path):
        raise ValueError('closure does not pin selected layout')
    checked = json.loads(layout_path.read_text())
    verify(checked['input_sha256']); verify(checked['artifacts'])
    for flag in ('assembled_drc_pass', 'assembled_lvs_pass', 'all_three_macros_expanded',
                 'all_source_macro_geometry_and_labels_preserved'):
        if checked.get(flag) is not True:
            raise ValueError('layout prerequisite missing: ' + flag)
    sources = source_pins()
    if any(checked['input_sha256'].get(k) != v for k, v in sources.items() if k != str(PROFILE)):
        raise ValueError('filled layout does not match current RTL source')
    recognized_profiles = [PROFILE, ROOT/'verification/signoff400/requirements.json',
                           ROOT/'verification/prototype_400mhz.json']
    geometry_profile = next((path for path in recognized_profiles
                             if checked['input_sha256'].get(str(path)) == sha(path)), None)
    if geometry_profile is None:
        raise ValueError('unknown or changed geometry profile')
    gds = layout / 'assembly.gds'
    if checked['artifacts'].get(str(gds)) != sha(gds):
        raise ValueError('layout does not pin selected GDS')
    manifest = dict(profile=str(PROFILE), profile_sha256=sha(PROFILE),
        candidate=dict(source_sha256=sources, physical_sha256={str(gds): sha(gds)}),
        evidence={}, handoff_artifacts={},
        imported_geometry=dict(path=str(receipt_path), sha256=sha(receipt_path),
            geometry_checks_pass=True, matching_current_source=True,
            geometry_profile=str(geometry_profile),geometry_profile_sha256=sha(geometry_profile),
            temperature_qualification_imported=False,
            applicability='checked geometry only; electrical, temperature and full process qualification remain open'),
        input_sha256={str(Path(__file__).resolve()): sha(Path(__file__).resolve()),
                      str(receipt_path): sha(receipt_path), str(layout_path): sha(layout_path)},
        release_qualified=False)
    out.mkdir(parents=True, exist_ok=False)
    save(out / 'manifest.json', manifest)
    save(out / 'functional_matrix.json', dict(profile_sha256=sha(PROFILE), cases=cases(), release_qualified=False))
    save(out / 'status.json', audit(manifest))
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--closure', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    a = parser.parse_args()
    prepare(a.closure, a.output)
    print(a.output.resolve() / 'manifest.json')
