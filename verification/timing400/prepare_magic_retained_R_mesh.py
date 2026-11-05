#!/usr/bin/env python3
"""Retain native wire segments for physical C mapping in an isolated extractor.

The ordinary simplify-off option still allows ResDoneWithNode's series,
parallel and triangle reductions. An explicit private diagnostic switch skips
that reduction stage, as the native geometry option already does, while keeping
normal .res.ext output and avoiding geometry mode's coordinate alignment.
This is an unqualified alternative R mesh, not an adopted runtime model.
"""
import difflib
from pathlib import Path
import subprocess
from check_compact_clock_tree import verify
from run_dco_qualification import ROOT, sha, save


def main():
    base = ROOT/'build/timing400/release_001'
    source = ROOT/'build/timing400/magic_location_source_001'
    previous = base/'magic_R_segment_trace_patch_001/assessment.json'
    for path, value in verify(previous)['diagnostic_source_files'].items():
        assert sha(path) == value
    path = source/'resis/ResMerge.c'
    original = subprocess.check_output(['git', '-C', str(source), 'show', '8.3.623:resis/ResMerge.c'], text=True)
    assert path.read_text() == original
    text = original.replace('#include <stdio.h>', '#include <stdio.h>\n#include <stdlib.h>', 1)
    marker = '    if (ResOptionsFlags & ResOpt_Geometry) return;'
    assert text.count(marker) == 1
    text = text.replace(marker, '    if ((ResOptionsFlags & ResOpt_Geometry) ||\n        getenv("OPENPLL_R_RETAIN_MESH")) return;')
    path.write_text(text)
    out = base/'magic_retained_R_mesh_patch_001'
    out.mkdir(exist_ok=False)
    files = ['resis/ResMerge.c', 'resis/ResMakeRes.c', 'resis/ResPrint.c', 'extract/ExtBasic.c', 'extract/ExtCouple.c', 'extract/ExtCell.c']
    patch = ''
    for name in files:
        native = subprocess.check_output(['git', '-C', str(source), 'show', '8.3.623:'+name], text=True)
        changed = (source/name).read_text()
        (out/('patched_'+Path(name).name)).write_text(changed)
        patch += ''.join(difflib.unified_diff(native.splitlines(True), changed.splitlines(True), fromfile='a/'+name, tofile='b/'+name))
    (out/'change.patch').write_text(patch)
    paths = [Path(__file__).resolve(), previous, source/'resis/resis.h', base/'DCO_R_segment_geometry_inspection_failure_001/assessment.json']
    save(out/'assessment.json', dict(input_sha256={str(p): sha(p) for p in paths},
        artifacts={str(p): sha(p) for p in out.iterdir()},
        diagnostic_source_files={str(source/f): sha(source/f) for f in files},
        opt_in_switch='OPENPLL_R_RETAIN_MESH',
        opt_in_skips_ResDoneWithNode_reductions=True, native_R_value_calculation_unchanged=True,
        normal_ext_output_preserved=True, geometry_coordinate_alignment_not_enabled=True,
        default_equivalence_and_retained_mesh_controls_required=True, release_qualified=False, adopted=False))
    print('Prepared opt-in unreduced R mesh extraction; controls required.')


if __name__ == '__main__':
    main()
