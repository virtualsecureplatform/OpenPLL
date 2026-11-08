"""Trace raw tile-area assignments with unchanged native R/C circuits."""
import argparse
import json
import os
import time
from collections import Counter
from pathlib import Path
from common_v3 import save, sha, verify
from resources import lease, identity
from compiled_charge_v2 import execute
from replay_keeper_flat_signed_C import TECH
from audit_keeper_native_R_contraction import parse
from audit_magic_resistance_area import audit


def signature(text):
    a = parse(text)
    devices = Counter((model, nodes, tuple(sorted(params.items()))) for model, nodes, params in a['devices'])
    caps = Counter((tuple(sorted((x, y))), v) for x, y, v in a['caps'])
    resistors = Counter((tuple(sorted((x, y))), v) for x, y, v in a['resistors'])
    return a['ports'], devices, caps, resistors


def run(engine, output):
    receipt = engine / 'assessment.json'
    e = json.loads(receipt.read_text())
    verify(e['input_sha256'])
    verify(e['artifacts'])
    if e['capacitance_equations_modified'] or e['release_tool_replaced']:
        raise ValueError('isolated observer required')
    binary = Path(e['installed_executable'])
    output.mkdir(parents=True, exist_ok=False)
    os.sched_setaffinity(0, {27})
    deadline = time.clock_gettime(time.CLOCK_BOOTTIME) + 600
    save(output / 'owner.json', dict(pid=os.getpid(), birth=identity(os.getpid())))
    pins = {str(p): sha(p) for p in [receipt, binary, TECH, Path(__file__).resolve(),
                                    Path(__file__).with_name('audit_magic_resistance_area.py'),
                                    Path(__file__).with_name('audit_keeper_native_R_contraction.py')]}
    artifacts = {}
    results = []
    try:
        for name, box_a, box_b in [('horizontal', '0 0 4000 100', '0 120 4000 220'),
                                    ('vertical', '0 0 100 4000', '120 0 220 4000'),
                                    ('dangling_tee', '0 0 4000 100', '0 120 4000 220')]:
            signatures = []
            details = None
            for enabled in (False, True):
                folder = output / (name + ('_on' if enabled else '_off'))
                folder.mkdir()
                rc = folder / 'minimal.magicrc'
                rc.write_text(f'tech load {{{TECH}}}\ndrc off\ncrashbackups disable\nlocking disable\n')
                script = folder / 'probe.tcl'
                model = folder / 'view.spice'
                trace = folder / 'area.jsonl'
                top = 'Area_' + name
                extra='box values 1900 -500 2100 0\npaint m1\nbox values '+box_a+'\n'if name=='dangling_tee'else''
                script.write_text(f'''cd {{{folder}}}
if {{[catch {{
load {top}
box values {box_a}
paint m1
{extra}label A center m1
port make 1
box values {box_b}
paint m1
label B center m1
port make 2
extract style ngspice()
extract do local
extract do capacitance
extract do coupling
extract no resistance
extresist include A
extresist simplify off
extract all
extresist all
ext2spice lvs
ext2spice hierarchy off
ext2spice subcircuit top on
ext2spice short resistor
ext2spice cthresh -1e100
ext2spice extresist on
ext2spice -o {{{model}}} {top}.ext
}} error]}} {{puts stderr $error; exit 1}}
quit -noprompt
''')
                pins.update({str(p): sha(p) for p in (rc, script)})
                verify(pins)
                os.environ.pop('OPENPLL_RESISTANCE_AREA_TRACE', None)
                if enabled:
                    os.environ['OPENPLL_RESISTANCE_AREA_TRACE'] = str(trace)
                save(output / 'status.json', dict(state='native_area_trace_control', case=name,
                                                  trace_enabled=enabled, release_ready=False))
                with lease(1, 4, deadline):
                    execute([binary, '-nowrapper', '-dnull', '-noconsole', '-rcfile', rc, script],
                            folder / 'native.log', deadline, 4)
                signatures.append(signature(model.read_text()))
                files = [model, folder / (top + '.ext'), folder / (top + '.res.ext'), folder / 'native.log']
                if enabled:
                    details = audit(trace)
                    files.append(trace)
                elif trace.exists():
                    raise ValueError('trace-off process wrote area log')
                artifacts.update({str(p): sha(p) for p in files})
            if signatures[0] != signatures[1]:
                raise ValueError('area observation changed native circuit')
            results.append(dict(case=name, exact_trace_off_on_R_C_device_and_port_match=True, area=details))
            save(output / 'progress.json', results)
        verify(pins)
        save(output / 'assessment.json', dict(input_sha256=pins, artifacts=artifacts, results=results,
                                              all_six_native_controls_complete=True,
                                              raw_area_logging_preserves_tested_circuits=True,
                                              merge_lineage_verified=False, capacitance_placement_qualified=False,
                                              distributed_wire_R_qualified=False, release_ready=False))
        save(output / 'status.json', dict(state='native_resistance_area_controls_complete', release_ready=False))
    except BaseException as error:
        save(output / 'status.json', dict(state='stopped_without_qualification', reason=repr(error), release_ready=False))
        raise


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    for name in ('engine', 'output'):
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()
    run(a.engine.resolve(), a.output.resolve())
