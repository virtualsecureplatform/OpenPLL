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
from native_spice_comments import strip_floating_annotation


def run():
    base=ROOT/'build/signoff400';out=base/'selected_reference_alias_separated_1761';out.mkdir(exist_ok=False)
    save(out/'owner.json',dict(pid=os.getpid(),birth=identity(os.getpid())))
    os.sched_setaffinity(0,{30});deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+1800
    try:
        engine=ROOT/'build/tools/magic_reference_alias_1757';owner=json.loads((engine/'owner.json').read_text())
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
        ext=out/'RotatedCrop.ext'
        fixture=original.read_text()
        substrate=[shlex.split(line) for line in fixture.splitlines() if line.startswith('substrate ')]
        if len(substrate)!=1:raise ValueError('one original global substrate reference required')
        refname=substrate[0][1];rx,ry=map(int,substrate[0][4:6]);layer=substrate[0][6]
        old=f'port "ALIAS_DRIVE" 0 {rx} {ry} {rx+1} {ry+1} {layer}'
        new=f'port "ALIAS_DRIVE" 0 {rx+2} {ry+2} {rx+3} {ry+3} {layer}'
        if fixture.count(old)!=1:raise ValueError('one explicit coincident fixture port required')
        ext.write_text(fixture.replace(old,new))
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
            # Direct C attachment is checked before any wire contraction.
            def cap_view(text, rename_reference):
                cards=['.subckt COnly ALIAS_DRIVE']
                for raw in text.splitlines():
                    line=strip_floating_annotation(raw).strip()
                    if line.startswith('C'):
                        f=line.split()
                        if rename_reference:
                            for i in [1,2]:
                                if f[i].lower()==refname.lower():f[i]='ALIAS_DRIVE'
                        cards.append(' '.join(f))
                return '\n'.join([*cards,'.ends COnly'])+'\n'
            cv_before=cap_view(before,False);cv_after=cap_view(after,True)
            direct_C=charge(cv_before,cv_after)
            for filename,text in [('C_reference_before.spice',cv_before),('C_reference_after.spice',cv_after)]:
                p=out/filename;p.write_text(text);artifacts[str(p)]=sha(p)
            data=parse(after);parent={};graph=defaultdict(set)
            def root(n):
                parent.setdefault(n,n)
                while parent[n]!=n:parent[n]=parent[parent[n]];n=parent[n]
                return n
            for a,b,v in data['resistors']:
                graph[a].add(b);graph[b].add(a)
                if v==0:parent[root(a)]=root(b)
            seen={refname.lower()};pending=list(seen)
            while pending:
                for other in graph[pending.pop()]:
                    if other not in seen:seen.add(other);pending.append(other)
            distinct=('alias_drive' in seen and root(refname.lower())!=root('alias_drive')
                and positions.get(refname)=={(str(rx),str(ry))}
                and positions.get('ALIAS_DRIVE')=={(str(rx+2),str(ry+2))})
            no_zero_fallback=all(a!='0' and b!='0' for a,b,v in data['caps'])
            attachment=distinct and no_zero_fallback and direct_C['native_devices_and_C_conserved']
            def branches(text):
                p=parse(text)
                return {k:Counter((tuple(sorted((a,b))),v) for a,b,v in p[k]) for k in ['resistors','caps']}
            results=dict(original_reference_attachment_verified=attachment,distinct_reference_and_port_points=distinct,no_default_zero_C_fallback=no_zero_fallback,direct_C_without_wire_contraction=direct_C,charge=charge(before,after),physical_connections=physical(before,after),wire_values=wires(native,after),
                passivity=assess_caps(parse(after)['caps']),duplicate_names_at_distinct_points={n:sorted(v) for n,v in positions.items() if len(v)>1},
                RC_branch_endpoints_values_unchanged=branches(after)==branches((baseline/'after.spice').read_text()),
                baseline_native_R_records_equal_diagnostic_only=Counter(s for s in native.splitlines() if s.startswith('resist '))==Counter(s for s in (baseline/'RotatedCrop.res.ext').read_text().splitlines() if s.startswith('resist ')),
                proven_reference_alias_records=[s for s in native.splitlines() if s.startswith('equiv ')],
                successful_native_network_markers=sum(s.startswith('subcap ') for s in native.splitlines()),
                port_rebuild_traces=[s for s in log.splitlines() if s.startswith('OPENPLL_RC_PORT_REBUILD')])
            passed=results['charge']['native_devices_and_C_conserved'] and results['physical_connections']['per_physical_device_connections_verified'] and results['wire_values']['per_native_wire_resistance_values_verified'] and results['passivity']['linear_C_PSD_certified'] and not results['duplicate_names_at_distinct_points'] and results['successful_native_network_markers']==1 and results['original_reference_attachment_verified']
            for p,digest in pins.items():
                if sha(p)!=digest:raise ValueError('input changed')
            save(out/'assessment.json',dict(input_sha256=pins,artifacts=artifacts,results=results,known_GDS_boundary_warnings=len(warnings),
                explicit_alias_end_to_end_RC_control_pass=passed,RC_export_fixed=False,release_ready=False))
            save(out/'status.json',dict(state='rebuilt_port_control_complete',all_control_checks_pass=passed))
            print(json.dumps(dict(passed=passed,formal_ports_match=results['charge']['formal_ports_match'],
                charge=results['charge']['native_devices_and_C_conserved'],RC_branches_unchanged=results['RC_branch_endpoints_values_unchanged'],
                native_R_records_unchanged=results['baseline_native_R_records_equal_diagnostic_only'],port_rebuild_traces=results['port_rebuild_traces']),indent=2))
            if not passed:raise ValueError('rebuilt port control failed')
    except BaseException as error:
        save(out/'status.json',dict(state='stopped_without_qualification',reason=repr(error)));raise

if __name__=='__main__':run()
