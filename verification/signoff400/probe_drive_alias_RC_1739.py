"""End-to-end native RC control for an explicit alias driver on a real crop."""
import json, os, shlex, time
from collections import defaultdict
from pathlib import Path
from runtime_common import ROOT, save, sha
from resources import identity, lease
from compiled_charge_v2 import execute
from replay_keeper_flat_signed_C import TECH
from native_C_roundoff import assess as charge
from native_physical_connections import assess as physical
from native_wire_values import assess as wires
from native_C_passivity_v2 import assess_caps
from audit_keeper_native_R_contraction import parse


def run():
    out = ROOT / 'build/signoff400/selected_drive_alias_RC_1739'
    out.mkdir(exist_ok=False)
    os.sched_setaffinity(0, {30})
    save(out / 'owner.json', dict(pid=os.getpid(), birth=identity(os.getpid())))
    try:
        source = ROOT / 'build/signoff400/selected_drive_alias_type_1731'
        receipt = source / 'assessment.json'; sr = json.loads(receipt.read_text())
        if not sr['explicit_alias_driver_type_control_pass']:
            raise ValueError('completed alias copy control required')
        original = source / 'magic_copy_trace_1723/RotatedCrop.ext'
        if sr['artifacts'][str(original)] != sha(original):
            raise ValueError('completed fixture changed')
        gds = ROOT / 'build/signoff400/selected_drive_type_RC_controls_1729/rotation0.gds'
        if sr['input_sha256'][str(gds)] != sha(gds):
            raise ValueError('completed source GDS changed')
        helpers = ['native_C_roundoff.py','native_physical_connections.py','native_wire_values.py',
                   'native_C_passivity_v2.py','native_device_identity.py','audit_keeper_native_R_contraction.py',
                   'compare_native_R_with_aliases.py','native_spice_comments.py']
        pins = {str(p): sha(p) for p in [receipt, original, gds, TECH, Path(__file__).resolve(),
                *(Path(__file__).with_name(n) for n in helpers)]}
        deadline = time.clock_gettime(time.CLOCK_BOOTTIME) + 300
        results = []
        for fixed, name in enumerate(['magic_indexed_RC_points_1708', 'magic_drive_type_1726']):
            engine = ROOT / 'build/tools' / name
            er = engine / 'assessment.json'; record = json.loads(er.read_text())
            binary, library = engine/'install/bin/magic', engine/'install/lib/magic/tcl/tclmagic.so'
            for p in [binary, library]:
                if record['artifacts'][str(p)] != sha(p): raise ValueError('native engine changed')
            pins.update({str(p): sha(p) for p in [er, binary, library]})
            case = out / name; case.mkdir()
            ext = case / 'RotatedCrop.ext'; ext.write_bytes(original.read_bytes())
            rc = case / 'minimal.magicrc'; rc.write_text(f'tech load {{{TECH}}}\ndrc off\ncrashbackups disable\nlocking disable\n')
            script = case / 'run.tcl'
            script.write_text(f'''cd {{{case}}}
if {{[catch {{
gds read {{{gds}}}
load RotatedCrop
select top cell
extract style ngspice()
extract no resistance
ext2spice lvs
ext2spice hierarchy off
ext2spice subcircuit top on
ext2spice short resistor
ext2spice cthresh -1e100
ext2spice extresist off
ext2spice -o before.spice RotatedCrop.ext
extresist simplify off
extresist threshold 0
extresist include ALIAS_DRIVE
extresist all
ext2spice extresist on
ext2spice -o after.spice RotatedCrop.ext
}} error]}} {{puts stderr $error;exit 1}}
quit -noprompt
''')
            pins.update({str(p): sha(p) for p in [ext, rc, script]})
            save(out/'status.json', dict(state='native_alias_RC_control_running', fixed=bool(fixed)))
            with lease(1, 4, deadline):
                execute(['env','-u','OPENPLL_RC_COPY_TRACE','-u','OPENPLL_RC_COPY_FROM_DRIVER',
                         '-u','OPENPLL_RC_COPY_PREFLIGHT_ONLY','OPENPLL_RC_NATIVE_CAPS=1',
                         'OPENPLL_RC_EXPLICIT_COUPLING=1','OPENPLL_RC_ZERO_JUNCTION=1',
                         'OPENPLL_RC_AREA_DIAGNOSTIC=1','OPENPLL_RC_DEVICE_ORIGINS=1',
                         str(binary),'-nowrapper','-dnull','-noconsole','-rcfile',str(rc),str(script)],
                        case/'native.log', deadline, 4)
            log = (case/'native.log').read_text()
            if not fixed:
                # The failed predecessor is evidence from its log only; no partial RC is accepted.
                results.append(dict(engine=name, missing_wire_failure_reproduced="Couldn't find wire" in log
                             and 'Error in extracting node' in log, partial_native_data_accepted=False))
                continue
            errors = [s for s in log.splitlines() if any(t in s.lower() for t in
                      ['error',"couldn't find wire", "couldn't find device",'orphaned node',
                       'missing terminal','not extracted as network','force label but no drive',
                       'openpll_rc_break_bounds','openpll_rc_negative_area','openpll_rc_bad_area',
                       'openpll_rc_bad_cap_budget','openpll_rc_empty_crossplane_overlap','openpll_rc_empty_driver_overlap'])]
            if errors:
                save(out/'native_failure.json',dict(errors=errors, partial_native_data_accepted=False))
                raise ValueError('candidate native alias RC failure')
            before, after = [(case/n).read_text() for n in ['before.spice','after.spice']]
            native = (case/'RotatedCrop.res.ext').read_text(); locations = defaultdict(set)
            for line in native.splitlines():
                if line.startswith('rnode '):
                    f = shlex.split(line); locations[f[1]].add(tuple(f[4:6]))
            result = dict(engine=name, charge=charge(before,after), physical_connections=physical(before,after),
                          wire_values=wires(native,after), passivity=assess_caps(parse(after)['caps']),
                          duplicate_names_at_distinct_points={n:sorted(v) for n,v in locations.items() if len(v)>1},
                          successful_native_network_markers=sum(s.startswith('subcap ') for s in native.splitlines()))
            results.append(result)
        fixed = results[1]
        passed = (results[0]['missing_wire_failure_reproduced']
                  and fixed['charge']['native_devices_and_C_conserved']
                  and fixed['physical_connections']['per_physical_device_connections_verified']
                  and fixed['wire_values']['per_native_wire_resistance_values_verified']
                  and fixed['passivity']['linear_C_PSD_certified']
                  and not fixed['duplicate_names_at_distinct_points']
                  and fixed['successful_native_network_markers']==1)
        for p,digest in pins.items():
            if sha(p)!=digest: raise ValueError('input changed')
        save(out/'assessment.json',dict(input_sha256=pins,results=results,
             artifacts={str(p):sha(p) for p in out.rglob('*') if p.is_file() and p.name not in ['owner.json','status.json'] and not p.name.endswith('.process.json')},
             explicit_alias_end_to_end_RC_control_pass=passed, RC_export_fixed=False, release_ready=False))
        save(out/'status.json',dict(state='alias_RC_control_complete',all_control_checks_pass=passed))
        print(json.dumps(dict(passed=passed,baseline_failure_reproduced=results[0]['missing_wire_failure_reproduced'],
                    native_network_markers=fixed['successful_native_network_markers']),indent=2))
        if not passed: raise ValueError('end-to-end explicit alias RC checks failed')
    except BaseException as error:
        save(out/'status.json',dict(state='stopped_without_qualification',reason=repr(error)))
        raise

if __name__=='__main__':run()
