#!/usr/bin/env python3
"""Trace the hierarchical device writer selected by ext2spice lvs defaults."""
import difflib
from pathlib import Path
import subprocess
from check_compact_clock_tree import verify
from run_dco_qualification import ROOT, sha, save


def main():
    base = ROOT/'build/timing400/release_001'
    source = ROOT/'build/timing400/magic_location_source_001'
    previous = base/'magic_R_binding_trace_patch_003/assessment.json'
    proof = verify(previous)
    for name, value in proof['diagnostic_source_files'].items():
        assert sha(name) == value
    flat = (source/'ext2spice/ext2spice.c').read_text()
    start = flat.index('    {\n        const char *trace_path = getenv("OPENPLL_SPICE_DEVICE_TRACE_FILE");')
    marker = '    /* Order and number of nodes in the output depends on the device class */'
    end = flat.index(marker, start)
    helper = flat[start:end]
    assert helper.count('OPENPLL_SPICE_DEVICE_TRACE_FILE') == 2
    helper = helper.replace('"%s%s", EFHNToStr(hierName), gate->dterm_attrs', '"%s", gate->dterm_attrs')
    path = source/'ext2spice/ext2hier.c'
    original = subprocess.check_output(['git', '-C', str(source), 'show', '8.3.623:ext2spice/ext2hier.c'], text=True)
    assert path.read_text() == original and original.count(marker) == 1
    changed = original.replace(marker, helper+marker)
    out = base/'magic_R_binding_trace_patch_004'
    out.mkdir(exist_ok=False)
    path.write_text(changed)
    files = [Path(p).relative_to(source) for p in proof['diagnostic_source_files']] + [Path('ext2spice/ext2hier.c')]
    patch = ''
    for name in files:
        native = subprocess.check_output(['git', '-C', str(source), 'show', '8.3.623:'+str(name)], text=True)
        patched = (source/name).read_text()
        (out/('patched_'+name.name)).write_text(patched)
        patch += ''.join(difflib.unified_diff(native.splitlines(True), patched.splitlines(True), fromfile='a/'+str(name), tofile='b/'+str(name)))
    (out/'change.patch').write_text(patch)
    paths = [Path(__file__).resolve(), previous, base/'DCO_original_device_geometry_ids_002/status.json',
             base/'DCO_retained_device_geometry_ids_001/status.json']
    save(out/'assessment.json', dict(input_sha256={str(p): sha(p) for p in paths},
        artifacts={str(p): sha(p) for p in out.iterdir()},
        diagnostic_source_files={str(source/f): sha(source/f) for f in files},
        hierarchical_and_flat_native_device_writers_traced=True,
        native_print_statements_and_arithmetic_unchanged=True, native_controls_required=True,
        release_qualified=False, adopted=False))
    print('Prepared device trace for the actual hierarchical LVS writer; output controls required.')


if __name__ == '__main__':
    main()
