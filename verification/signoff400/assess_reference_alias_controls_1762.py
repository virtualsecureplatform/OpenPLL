"""Independent geometry, charge, terminal, branch, passivity and C-attachment controls."""
import json,shlex,time,os
from collections import defaultdict
from pathlib import Path
from runtime_common import ROOT,save,sha
from resources import lease
from native_C_roundoff import assess
from native_C_passivity_v2 import assess_caps
from native_physical_connections import assess as physical
from native_wire_values import assess as wires
from audit_keeper_native_R_contraction import parse


def run():
    base=ROOT/'build/signoff400';controls=base/'selected_reference_alias_RC_controls_1760'
    focused=[base/'selected_reference_alias_RC_1758/assessment.json',base/'selected_reference_alias_separated_1761/assessment.json',base/'selected_reference_alias_stress_1759/assessment.json']
    receipt=controls/'assessment.json';record=json.loads(receipt.read_text())
    paths=[receipt,*focused,Path(__file__).resolve(),*[Path(__file__).with_name(n) for n in ['native_C_roundoff.py',
        'native_C_passivity_v2.py','native_physical_connections.py','native_wire_values.py','native_device_identity.py',
        'audit_keeper_native_R_contraction.py','compare_native_R_with_aliases.py','native_spice_comments.py']]]
    for p in [receipt,*focused]:
        data=json.loads(p.read_text())
        for name,digest in {**data['input_sha256'],**data['artifacts']}.items():
            if sha(name)!=digest:raise ValueError('completed control changed: '+name)
    pins={str(p):sha(p) for p in paths};out=base/'selected_reference_alias_control_assessment_1762';out.mkdir(exist_ok=False)
    results=[];os.sched_setaffinity(0,{30})
    with lease(1,4,time.clock_gettime(time.CLOCK_BOOTTIME)+600):
        for angle in range(4):
            case=controls/f'rotation{angle}_fixed1';before,after=[(case/n).read_text() for n in ['before.spice','after.spice']]
            native=(case/'RotatedCrop.res.ext').read_text();positions=defaultdict(set)
            for line in native.splitlines():
                if line.startswith('rnode '):
                    f=shlex.split(line);positions[f[1]].add(tuple(f[4:6]))
            row=next(r for r in record['results'] if r['rotation_degrees']==angle*90 and r['fixed'])
            geometry={k:row[k] for k in ['out_of_bounds_breakpoints','negative_raw_area_nodes','empty_crossplane_overlaps',
                'empty_driver_overlaps','invalid_area_budgets','invalid_capacitance_budgets']}
            log=(case/'native.log').read_text()
            native_errors=[s for s in log.splitlines() if any(t in s.lower() for t in ["couldn't find wire", "couldn't find device",'error in extracting node','orphaned node','missing terminal','not extracted as network','force label but no drive','openpll_rc_reference_error'])]
            results.append(dict(rotation=angle*90,geometry=geometry,charge=assess(before,after),
                physical_connections=physical(before,after),wire_values=wires(native,after),passivity=assess_caps(parse(after)['caps']),
                duplicate_names_at_distinct_points={n:sorted(v) for n,v in positions.items() if len(v)>1},native_extraction_errors=native_errors))
        f=[json.loads(p.read_text()) for p in focused]
        checks=dict(coincident_reference_alias_RC_verified=f[0]['explicit_alias_end_to_end_RC_control_pass'],
            separated_reference_alias_RC_verified=f[1]['explicit_alias_end_to_end_RC_control_pass'],
            original_C_attachment_before_wire_contraction_verified=f[1]['results']['original_reference_attachment_verified'],
            full_65_port_1000_label_analytical_wire_verified=f[2]['all_65_port_controls_pass'],
            all_four_rotations_geometry_clean=all(not any(r['geometry'].values()) for r in results),
            all_four_rotations_charge_and_ports_preserved=all(r['charge']['native_devices_and_C_conserved'] for r in results),
            all_four_rotations_physical_terminals_verified=all(r['physical_connections']['per_physical_device_connections_verified'] and r['physical_connections']['physical_devices_checked']==34 for r in results),
            every_native_wire_branch_preserved=all(r['wire_values']['per_native_wire_resistance_values_verified'] for r in results),
            all_four_rotations_C_PSD=all(r['passivity']['linear_C_PSD_certified'] for r in results),
            all_named_physical_points_unique=all(not r['duplicate_names_at_distinct_points'] for r in results),
            no_native_conductor_or_reference_errors=all(not r['native_extraction_errors'] for r in results))
        for p,digest in pins.items():
            if sha(p)!=digest:raise ValueError('assessment input changed')
        save(out/'assessment.json',dict(input_sha256=pins,results=results,checks=checks,all_control_checks_pass=all(checks.values()),
            RC_export_fixed=False,release_ready=False))
        print(json.dumps(dict(all_control_checks_pass=all(checks.values()),checks=checks),indent=2))
        if not all(checks.values()):raise ValueError('reference alias controls failed')

if __name__=='__main__':run()
