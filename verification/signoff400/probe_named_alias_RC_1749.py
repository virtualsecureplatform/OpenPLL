"""Fresh native RC case for port metadata lost while rebuilding a killed alias."""
import json, os, re, shlex, time
from collections import Counter, defaultdict
from pathlib import Path
from runtime_common import ROOT,save,sha
from resources import identity,lease
from compiled_charge_v2 import execute
from replay_keeper_flat_signed_C import TECH
from native_C_roundoff import assess as charge
from native_physical_connections import assess as physical
from native_wire_values import assess as wires
from native_C_passivity_v2 import assess_caps
from audit_keeper_native_R_contraction import parse


def run():
    base=ROOT/'build/signoff400';out=base/'selected_named_alias_RC_1749';out.mkdir(exist_ok=False)
    save(out/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    os.sched_setaffinity(0,{30});deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+1800
    try:
        engine=ROOT/'build/tools/magic_named_alias_1748';owner=json.loads((engine/'owner.json').read_text())
        save(out/'status.json',dict(state='waiting_for_live_rebuilt_port_build'))
        while not (engine/'assessment.json').exists():
            if identity(owner['pid'])!=owner['birth']:raise ValueError('build ended without receipt')
            if json.loads((engine/'status.json').read_text())['state']=='stopped_without_qualification':raise ValueError('build failed')
            if time.clock_gettime(time.CLOCK_BOOTTIME)>=deadline:raise TimeoutError('build admission deadline')
            time.sleep(5)
        old=base/'selected_drive_alias_RC_assessment_1740';receipt=old/'assessment.json';record=json.loads(receipt.read_text())
        for name,digest in {**record['input_sha256'],**record['artifacts']}.items():
            if sha(name)!=digest:raise ValueError('completed baseline changed')
        if not record['baseline_missing_wire_failure_reproduced'] or record['results']['charge']['formal_ports_match']:
            raise ValueError('recorded missing-port regression required')
        original=base/'selected_drive_alias_type_1731/magic_copy_trace_1723/RotatedCrop.ext'
        gds=base/'selected_drive_type_RC_controls_1729/rotation0.gds'
        fixture_receipt=base/'selected_drive_alias_type_1731/assessment.json';fr=json.loads(fixture_receipt.read_text())
        if fr['artifacts'][str(original)]!=sha(original) or fr['input_sha256'][str(gds)]!=sha(gds):raise ValueError('fixture changed')
        binary,library=engine/'install/bin/magic',engine/'install/lib/magic/tcl/tclmagic.so'
        er=engine/'assessment.json';data=json.loads(er.read_text())
        for p in [binary,library]:
            if data['artifacts'][str(p)]!=sha(p):raise ValueError('engine changed')
        ext=out/'RotatedCrop.ext';ext.write_bytes(original.read_bytes())
        rc=out/'minimal.magicrc';rc.write_text(f'tech load {{{TECH}}}\ndrc off\ncrashbackups disable\nlocking disable\n')
        script=out/'run.tcl'
        baseline=base/'selected_drive_alias_RC_1739/magic_drive_type_1726'
        script.write_text((baseline/'run.tcl').read_text().replace(str(baseline),str(out)))
        helpers=['compiled_charge_v2.py','native_C_roundoff.py','native_physical_connections.py','native_wire_values.py',
            'native_C_passivity_v2.py','native_device_identity.py','audit_keeper_native_R_contraction.py','compare_native_R_with_aliases.py','native_spice_comments.py']
        paths=[receipt,fixture_receipt,original,gds,TECH,binary,library,er,rc,script,ext,Path(__file__).resolve(),
               *(Path(__file__).with_name(n) for n in helpers)]
        pins={str(p):sha(p) for p in paths}
        save(out/'inputs.json',dict(input_sha256=pins,maximum_native_cases=1,automatic_identical_retry=False,
            physical_geometry_unchanged=True,source_change='preserve rebuilt explicit port metadata'))
        with lease(1,4,deadline):
            save(out/'status.json',dict(state='native_rebuilt_port_control_running'))
            execute(['env','-u','OPENPLL_RC_COPY_TRACE','-u','OPENPLL_RC_COPY_FROM_DRIVER','-u','OPENPLL_RC_COPY_PREFLIGHT_ONLY',
                'OPENPLL_RC_NATIVE_CAPS=1','OPENPLL_RC_EXPLICIT_COUPLING=1','OPENPLL_RC_ZERO_JUNCTION=1',
                'OPENPLL_RC_AREA_DIAGNOSTIC=1','OPENPLL_RC_DEVICE_ORIGINS=1','OPENPLL_RC_PORT_REBUILD_TRACE=1',
                str(binary),'-nowrapper','-dnull','-noconsole','-rcfile',str(rc),str(script)],out/'native.log',min(deadline,time.clock_gettime(time.CLOCK_BOOTTIME)+120),4)
        artifacts={str(out/n):sha(out/n) for n in ['before.spice','after.spice','RotatedCrop.res.ext','native.log']}
        save(out/'native_completion.json',dict(input_sha256=pins,artifacts=artifacts,native_process_completed=True))
        log=(out/'native.log').read_text()
        boundary=re.compile(r'^Error while reading cell "RotatedCrop" \(byte position \d+\): Warning:  Cell RotatedCrop boundary was redefined\.$')
        summary='CIF file read error: Warning:  Cell RotatedCrop boundary was redefined.'
        warnings=[];errors=[]
        for line in log.splitlines():
            if boundary.fullmatch(line) or line==summary:warnings.append(line)
            elif any(t in line.lower() for t in ['error',"couldn't find wire", "couldn't find device",'orphaned node',
                'missing terminal','not extracted as network','force label but no drive','openpll_rc_break_bounds',
                'openpll_rc_negative_area','openpll_rc_bad_area','openpll_rc_bad_cap_budget',
                'openpll_rc_empty_crossplane_overlap','openpll_rc_empty_driver_overlap']):errors.append(line)
        if errors:raise ValueError('native failures: '+repr(errors[:3]))
        with lease(1,4,deadline):
            before,after=[(out/n).read_text() for n in ['before.spice','after.spice']]
            native=(out/'RotatedCrop.res.ext').read_text();positions=defaultdict(set)
            for line in native.splitlines():
                if line.startswith('rnode '):
                    f=shlex.split(line);positions[f[1]].add(tuple(f[4:6]))
            def branches(text):
                p=parse(text)
                return {k:Counter((tuple(sorted((a,b))),v) for a,b,v in p[k]) for k in ['resistors','caps']}
            results=dict(charge=charge(before,after),physical_connections=physical(before,after),wire_values=wires(native,after),
                passivity=assess_caps(parse(after)['caps']),duplicate_names_at_distinct_points={n:sorted(v) for n,v in positions.items() if len(v)>1},
                RC_branch_endpoints_values_unchanged=branches(after)==branches((baseline/'after.spice').read_text()),
                native_R_records_unchanged=Counter(native.splitlines())==Counter((baseline/'RotatedCrop.res.ext').read_text().splitlines()),
                successful_native_network_markers=sum(s.startswith('subcap ') for s in native.splitlines()),
                port_rebuild_traces=[s for s in log.splitlines() if s.startswith('OPENPLL_RC_PORT_REBUILD')])
            passed=results['charge']['native_devices_and_C_conserved'] and results['physical_connections']['per_physical_device_connections_verified'] and results['wire_values']['per_native_wire_resistance_values_verified'] and results['passivity']['linear_C_PSD_certified'] and not results['duplicate_names_at_distinct_points'] and results['successful_native_network_markers']==1 and results['native_R_records_unchanged']
            for p,digest in pins.items():
                if sha(p)!=digest:raise ValueError('input changed')
            save(out/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,results=results,known_GDS_boundary_warnings=len(warnings),
                explicit_alias_end_to_end_RC_control_pass=passed,RC_export_fixed=False,release_ready=False))
            save(out/'status.json',dict(state='rebuilt_port_control_complete',all_control_checks_pass=passed))
            print(json.dumps(dict(passed=passed,formal_ports_match=results['charge']['formal_ports_match'],
                charge=results['charge']['native_devices_and_C_conserved'],RC_branches_unchanged=results['RC_branch_endpoints_values_unchanged'],
                native_R_records_unchanged=results['native_R_records_unchanged'],port_rebuild_traces=results['port_rebuild_traces']),indent=2))
            if not passed:raise ValueError('rebuilt port control failed')
    except BaseException as error:
        save(out/'status.json',dict(state='stopped_without_qualification',reason=repr(error)));raise

if __name__=='__main__':run()
