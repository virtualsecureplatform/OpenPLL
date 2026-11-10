"""Recover normal native completion after the1739 log-classifier analysis stop."""
import json, os, re, shlex, time
from collections import defaultdict
from pathlib import Path
from runtime_common import ROOT,save,sha
from resources import identity,lease
from native_C_roundoff import assess as charge
from native_physical_connections import assess as physical
from native_wire_values import assess as wires
from native_C_passivity_v2 import assess_caps
from audit_keeper_native_R_contraction import parse


def run():
    base=ROOT/'build/signoff400';source=base/'selected_drive_alias_RC_1739'
    status=source/'status.json';owner=json.loads((source/'owner.json').read_text())
    if identity(owner['pid'])==owner['birth']:raise ValueError('controller still live')
    if json.loads(status.read_text())!={'state':'stopped_without_qualification','reason':"ValueError('candidate native alias RC failure')"}:
        raise ValueError('exact post-execute classifier stop required')
    script=Path(__file__).with_name('probe_drive_alias_RC_1739.py')
    if script.read_text().count("raise ValueError('candidate native alias RC failure')")!=1:
        raise ValueError('unique observed post-execute stop required')
    copy=base/'selected_drive_alias_type_1731';cr=copy/'assessment.json';record=json.loads(cr.read_text())
    original=copy/'magic_copy_trace_1723/RotatedCrop.ext'
    if record['artifacts'][str(original)]!=sha(original):raise ValueError('fixture changed')
    cases=[source/name for name in ['magic_indexed_RC_points_1708','magic_drive_type_1726']]
    for case in cases:
        process=json.loads((case/'native.process.json').read_text())
        if identity(process['pid'])==process['birth']:raise ValueError('native producer still live')
        if sha(case/'RotatedCrop.ext')!=sha(original):raise ValueError('fixture not preserved')
    out=base/'selected_drive_alias_RC_assessment_1740';out.mkdir(exist_ok=False)
    paths=[status,source/'owner.json',source/'native_failure.json',script,cr,original,Path(__file__).resolve()]
    for case in cases:paths.extend([case/'native.process.json',case/'native.log',case/'run.tcl',case/'minimal.magicrc',case/'RotatedCrop.ext'])
    paths.extend([Path(__file__).with_name(n) for n in ['compiled_charge_v2.py','native_C_roundoff.py',
        'native_physical_connections.py','native_wire_values.py','native_C_passivity_v2.py',
        'native_device_identity.py','audit_keeper_native_R_contraction.py','compare_native_R_with_aliases.py','native_spice_comments.py']])
    pins={str(p):sha(p) for p in paths}
    # Both execute() calls returned normally before the unique observed error
    # branch. A nonzero native exit would have raised a different RuntimeError.
    # This is a recovery receipt, not a backdated original producer receipt.
    save(out/'native_completion_recovery.json',dict(native_process_completed=True,
        original_controller_analysis_stopped=True,completion_evidence='observed unique classifier exception after both execute calls returned normally',
        input_sha256=pins,partial_failed_baseline_RC_accepted=False,native_extraction_rerun=False))
    boundary=re.compile(r'^Error while reading cell "RotatedCrop" \(byte position \d+\): Warning:  Cell RotatedCrop boundary was redefined\.$')
    summary='CIF file read error: Warning:  Cell RotatedCrop boundary was redefined.'
    log=(cases[1]/'native.log').read_text();warnings=[];errors=[]
    for line in log.splitlines():
        if boundary.fullmatch(line) or line==summary:warnings.append(line)
        elif any(t in line.lower() for t in ['error',"couldn't find wire", "couldn't find device",'orphaned node',
            'missing terminal','not extracted as network','force label but no drive','openpll_rc_break_bounds',
            'openpll_rc_negative_area','openpll_rc_bad_area','openpll_rc_bad_cap_budget',
            'openpll_rc_empty_crossplane_overlap','openpll_rc_empty_driver_overlap']):errors.append(line)
    if errors:raise ValueError('other native error: '+repr(errors[:3]))
    baseline=(cases[0]/'native.log').read_text()
    failed="Couldn't find wire at 106400 64915" in baseline and 'Error in extracting node a_106400_64915#' in baseline
    os.sched_setaffinity(0,{30})
    with lease(1,4,time.clock_gettime(time.CLOCK_BOOTTIME)+300):
        before,after=[(cases[1]/n).read_text() for n in ['before.spice','after.spice']]
        native=(cases[1]/'RotatedCrop.res.ext').read_text();positions=defaultdict(set)
        for line in native.splitlines():
            if line.startswith('rnode '):
                f=shlex.split(line);positions[f[1]].add(tuple(f[4:6]))
        results=dict(charge=charge(before,after),physical_connections=physical(before,after),
            wire_values=wires(native,after),passivity=assess_caps(parse(after)['caps']),
            duplicate_names_at_distinct_points={n:sorted(v) for n,v in positions.items() if len(v)>1},
            successful_native_network_markers=sum(s.startswith('subcap ') for s in native.splitlines()))
        passed=failed and results['charge']['native_devices_and_C_conserved'] and results['physical_connections']['per_physical_device_connections_verified'] and results['wire_values']['per_native_wire_resistance_values_verified'] and results['passivity']['linear_C_PSD_certified'] and not results['duplicate_names_at_distinct_points'] and results['successful_native_network_markers']==1
        pins.update({str(cases[1]/n):sha(cases[1]/n) for n in ['before.spice','after.spice','RotatedCrop.res.ext']})
        for p,digest in pins.items():
            if sha(p)!=digest:raise ValueError('completed input changed')
        save(out/'assessment.json',dict(input_sha256=pins,results=results,baseline_missing_wire_failure_reproduced=failed,
            known_GDS_boundary_warnings=len(warnings),other_native_error_lines=errors,
            artifacts={str(out/'native_completion_recovery.json'):sha(out/'native_completion_recovery.json')},
            explicit_alias_end_to_end_RC_control_pass=passed,native_extraction_rerun=False,RC_export_fixed=False,release_ready=False))
        print(json.dumps(dict(passed=passed,baseline_failure_reproduced=failed,
            charge=results['charge']['native_devices_and_C_conserved'],physical=results['physical_connections']['per_physical_device_connections_verified'],
            wires=results['wire_values']['per_native_wire_resistance_values_verified'],passivity=results['passivity']['linear_C_PSD_certified'],
            native_network_markers=results['successful_native_network_markers']),indent=2))
        if not passed:raise ValueError('end-to-end alias RC checks failed')

if __name__=='__main__':run()
