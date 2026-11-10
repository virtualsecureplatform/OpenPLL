"""Native real-crop control for explicit port aliases after device selection."""
import json, os, shlex, time
from pathlib import Path
from runtime_common import ROOT, save, sha
from resources import lease, identity
from compiled_charge_v2 import execute
from replay_keeper_flat_signed_C import TECH


def run():
    out = ROOT / 'build/signoff400/selected_drive_alias_type_1731'
    out.mkdir(exist_ok=False)
    os.sched_setaffinity(0, {30})
    save(out / 'owner.json', dict(pid=os.getpid(), birth=identity(os.getpid())))
    source = ROOT / 'build/signoff400/selected_drive_type_RC_controls_1729'
    receipt = source / 'assessment.json'
    record = json.loads(receipt.read_text())
    gds = source / 'rotation0.gds'
    original = source / 'rotation0_fixed0/RotatedCrop.ext'
    for p in [gds, original]:
        if record['artifacts'][str(p)] != sha(p):
            raise ValueError('completed crop changed')
    text = original.read_text()
    substrate = [shlex.split(s) for s in text.splitlines() if s.startswith('substrate ')]
    if len(substrate) != 1:
        raise ValueError('exactly one native substrate anchor required')
    row = substrate[0]; name, x, y, layer = row[1], int(row[4]), int(row[5]), row[6]
    # This fixture adds one explicit port alias at the original native anchor;
    # it does not add conductor paint, devices, capacitance or a layout short.
    fixture = text + f'\nport "ALIAS_DRIVE" 0 {x} {y} {x+1} {y+1} {layer}\nequiv "{name}" "ALIAS_DRIVE"\n'
    deadline = time.clock_gettime(time.CLOCK_BOOTTIME) + 300
    pins = {str(p): sha(p) for p in [receipt, gds, original, TECH, Path(__file__).resolve()]}
    results = []
    for engine_name in ['magic_copy_trace_1723', 'magic_drive_type_1726']:
        engine = ROOT / 'build/tools' / engine_name
        er = engine / 'assessment.json'; data = json.loads(er.read_text())
        binary, library = engine / 'install/bin/magic', engine / 'install/lib/magic/tcl/tclmagic.so'
        for p in [binary, library]:
            if data['artifacts'][str(p)] != sha(p): raise ValueError('engine changed')
        pins.update({str(p): sha(p) for p in [er, binary, library]})
        case = out / engine_name; case.mkdir()
        ext = case / 'RotatedCrop.ext'; ext.write_text(fixture)
        rc = case / 'minimal.magicrc'; rc.write_text(f'tech load {{{TECH}}}\ndrc off\ncrashbackups disable\nlocking disable\n')
        script = case / 'run.tcl'
        script.write_text(f'''cd {{{case}}}
gds read {{{gds}}}
load RotatedCrop
select top cell
extract style ngspice()
extresist simplify off
extresist threshold 0
extresist include ALIAS_DRIVE
extresist all
quit -noprompt
''')
        pins.update({str(p): sha(p) for p in [ext, rc, script]})
        with lease(1, 4, deadline):
            execute(['env', 'OPENPLL_RC_NATIVE_CAPS=1', 'OPENPLL_RC_EXPLICIT_COUPLING=1',
                     'OPENPLL_RC_ZERO_JUNCTION=1', 'OPENPLL_RC_COPY_TRACE=1',
                     'OPENPLL_RC_COPY_FROM_DRIVER=1', 'OPENPLL_RC_COPY_PREFLIGHT_ONLY=1',
                     str(binary), '-nowrapper', '-dnull', '-noconsole', '-rcfile', str(rc), str(script)],
                    case / 'native.log', deadline, 4)
        traces = [s for s in (case / 'native.log').read_text().splitlines() if s.startswith('OPENPLL_RC_COPY_TRACE ')]
        results.append(dict(engine=engine_name, traces=traces))
    for p, digest in pins.items():
        if sha(p) != digest: raise ValueError('input changed')
    # Require the native copy to complete and report the original physical layer.
    def end(row):
        lines = [s for s in row['traces'] if 'stage=end ' in s]
        if len(lines) != 1: raise ValueError('one completed copy required')
        return dict(token.split('=', 1) for token in lines[0].split()[1:])
    old, new = [end(r) for r in results]
    passed = old['expected'] != new['expected'] and new['expected'] in [new['found_left'], new['found_right']] and new['found_left'] != 'space'
    save(out / 'assessment.json', dict(input_sha256=pins, results=results,
         fixture_original_anchor=dict(name=name, x=x, y=y, EXT_layer=layer),
         explicit_alias_driver_type_control_pass=passed,
         artifacts={str(p): sha(p) for p in out.rglob('*') if p.is_file() and not p.name.endswith('.process.json')},
         copy_only=True, RC_export_fixed=False, release_ready=False))
    print(json.dumps(dict(passed=passed, results=results), indent=2))
    if not passed: raise ValueError('explicit alias driver control failed')

if __name__ == '__main__': run()
