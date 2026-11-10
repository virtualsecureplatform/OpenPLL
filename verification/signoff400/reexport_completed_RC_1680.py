"""Re-export completed native RC geometry with the corrected wire-unit reader.

This never runs geometry extraction and refuses incomplete producer artifacts.
The resulting netlist still requires the full electrical/coverage audit.
"""
import json
import os
import shutil
import time
from pathlib import Path

from runtime_common import ROOT, save, sha
from resources import identity, lease
from compiled_charge_v2 import execute
from replay_keeper_flat_signed_C import TECH
from extract_keeper_flat_geometry_C import FLAT


def run():
    source = ROOT / 'build/signoff400/selected_corrected_full_RC_1671'
    receipt = source / 'assessment.json'
    record = json.loads(receipt.read_text())
    if record.get('native_process_completed') is not True:
        raise ValueError('normal completed native geometry receipt required')
    process = json.loads((source / 'native.process.json').read_text())
    if identity(process['pid']) == process['birth']:
        raise ValueError('producer still live; active artifacts cannot be consumed')
    engine = ROOT / 'build/tools/magic_wire_units_1678'
    engine_receipt = engine / 'assessment.json'
    er = json.loads(engine_receipt.read_text())
    unit_receipt = ROOT / 'build/signoff400/selected_corrected_wire_R_units_1679/assessment.json'
    if json.loads(unit_receipt.read_text()).get('native_wire_units_preserved_to_float32_precision') is not True:
        raise ValueError('corrected native wire-unit control required')
    binary = engine / 'install/bin/magic'
    library = engine / 'install/lib/magic/tcl/tclmagic.so'
    for path in (binary, library):
        if sha(path) != er['artifacts'][str(path)]:
            raise ValueError('engine artifact changed: ' + str(path))
    ext = source / (FLAT + '.ext')
    res = source / (FLAT + '.res.ext')
    if sha(res) != record['artifacts'][str(res)]:
        raise ValueError('completed native resistance geometry changed')
    original = ROOT / 'build/signoff400/selected_keeper_contact_corrected_C_1573' / ext.name
    if sha(ext) != record['input_sha256'][str(original)]:
        raise ValueError('source capacitance geometry changed')
    for name, digest in record['input_sha256'].items():
        if sha(Path(name)) != digest:
            raise ValueError('producer input changed: ' + name)

    out = ROOT / 'build/signoff400/selected_completed_RC_reexport_1680'
    out.mkdir(exist_ok=False)
    save(out / 'owner.json', dict(pid=os.getpid(), birth=identity(os.getpid())))
    try:
        for path in (ext, res):
            shutil.copyfile(path, out / path.name)
        rc = out / 'minimal.magicrc'
        rc.write_text(f'tech load {{{TECH}}}\ndrc off\ncrashbackups disable\nlocking disable\n')
        script = out / 'run.tcl'
        script.write_text(f'''cd {{{out}}}
if {{[catch {{
load {FLAT}
scalegrid 1 2
extract style ngspice()
ext2spice lvs
ext2spice hierarchy off
ext2spice subcircuit top on
ext2spice short resistor
ext2spice cthresh -1e100
ext2spice extresist on
ext2spice -o after.spice {FLAT}.ext
}} error]}} {{puts stderr $error;exit 1}}
quit -noprompt
''')
        pinned = [receipt, engine_receipt, unit_receipt, binary, library,
                  ext, res, TECH, rc, script, Path(__file__).resolve()]
        pins = {str(path): sha(path) for path in pinned}
        save(out / 'inputs.json', dict(input_sha256=pins, geometry_reused=True,
             geometry_extraction_invoked=False, RC_export_fixed=False, release_ready=False))
        deadline = time.clock_gettime(time.CLOCK_BOOTTIME) + 1800
        with lease(1, 16, deadline):
            save(out / 'status.json', dict(state='completed_geometry_reexport_running'))
            execute(['env', 'OPENPLL_RC_EXPLICIT_COUPLING=1',
                     'OPENPLL_RC_NATIVE_CAPS=1', 'OPENPLL_RC_ZERO_JUNCTION=1',
                     'OPENPLL_RC_DEVICE_ORIGINS=1', str(binary), '-nowrapper',
                     '-dnull', '-noconsole', '-rcfile', str(rc), str(script)],
                    out / 'native.log', deadline, 16)
        for name, digest in pins.items():
            if sha(Path(name)) != digest:
                raise ValueError('re-export input changed: ' + name)
        for path in (ext, res):
            if sha(out / path.name) != sha(path):
                raise ValueError('local native geometry changed')
        files = [out / 'after.spice', out / 'native.log']
        save(out / 'assessment.json', dict(input_sha256=pins,
             artifacts={str(path): sha(path) for path in files},
             native_process_completed=True, geometry_extraction_invoked=False,
             full_export_audited=False, RC_export_fixed=False, release_ready=False))
        save(out / 'status.json', dict(state='reexport_complete_audit_pending'))
    except BaseException as error:
        save(out / 'status.json', dict(state='stopped_without_qualification', reason=repr(error)))
        raise


if __name__ == '__main__':
    run()
